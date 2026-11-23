"""Read-only facts about a git repository: files, owners, in-flight branches, imports.

Everything here is plain git; no AI and no GitHub API.
"""
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def list_files(repo, commit="HEAD"):
    return git(repo, "ls-tree", "-r", "--name-only", commit).splitlines()


def default_base(repo):
    for ref in ("origin/main", "main", "origin/master", "master"):
        if subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "-q", ref],
                          capture_output=True).returncode == 0:
            return ref
    return "HEAD"


def current_user(repo):
    try:
        return git(repo, "config", "user.name").strip()
    except RuntimeError:
        return ""


def recent_authors(repo, days=90, commit="HEAD"):
    """{path: Counter(author -> number of commits touching it in the last `days`)}"""
    out = git(repo, "log", commit, f"--since={days}.days", "--name-only", "--format=@@%an")
    authors = defaultdict(Counter)
    current = None
    for line in out.splitlines():
        if line.startswith("@@"):
            current = line[2:]
        elif line.strip() and current:
            authors[line.strip()][current] += 1
    return authors


# ---------- CODEOWNERS ----------

def read_codeowners(repo, commit="HEAD"):
    """List of (pattern, [owners]); later rules win, as on GitHub."""
    for loc in ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"):
        try:
            text = git(repo, "show", f"{commit}:{loc}")
        except RuntimeError:
            continue
        rules = []
        for line in text.splitlines():
            parts = line.split("#", 1)[0].split()
            if len(parts) >= 2:
                rules.append((parts[0], parts[1:]))
        return rules
    return []


def _pattern_matches(pattern, path):
    anchored = pattern.startswith("/")
    p = pattern.strip("/")
    if pattern.endswith("/"):  # directory
        return path.startswith(p + "/") if anchored else (f"/{p}/" in f"/{path}")
    if fnmatch(path, p) or path.startswith(p + "/"):
        return True
    return not anchored and "/" not in p and fnmatch(PurePosixPath(path).name, p)


def owners_for(rules, path):
    owners = []
    for pattern, who in rules:
        if _pattern_matches(pattern, path):
            owners = who
    return owners


# ---------- in-flight branches ----------

@dataclass
class Branch:
    name: str
    author: str
    files: list


def in_flight_branches(repo, base):
    """Branches not yet merged into `base`, with the files each one changes."""
    refs = git(repo, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes").split()
    base_key = base.split("/", 1)[1] if base.startswith("origin/") else base
    seen, branches = set(), []
    for ref in refs:
        if ref.endswith("/HEAD"):
            continue
        short = ref.removeprefix("refs/heads/").removeprefix("refs/remotes/")
        key = short.split("/", 1)[1] if ref.startswith("refs/remotes/") else short
        if key == base_key or key in seen:
            continue
        seen.add(key)
        merged = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", short, base],
                                capture_output=True).returncode == 0
        if merged:
            continue
        files = git(repo, "diff", "--name-only", f"{base}...{short}").splitlines()
        if files:
            author = git(repo, "log", "-1", "--format=%an", short).strip()
            branches.append(Branch(short, author, files))
    return branches


# ---------- import graph (Python + JS/TS) ----------

PY_IMPORT = re.compile(r"^\s*(?:from\s+(\.*[\w.]*)\s+import\s+([\w, ]+)|import\s+([\w.]+))", re.M)
JS_IMPORT = re.compile(r"""(?:from\s+|require\(\s*|import\s*\(?\s*)['"](\.{1,2}/[^'"]+)['"]""")
JS_EXTS = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", "/index.ts", "/index.tsx", "/index.js", "/index.jsx")
SOURCE_EXTS = (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs")


def read_blobs(repo, commit, paths):
    """Read many files at `commit` in one git process."""
    data = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"],
                          input="".join(f"{commit}:{p}\n" for p in paths).encode(),
                          capture_output=True, check=True).stdout
    out, i = {}, 0
    for p in paths:
        nl = data.index(b"\n", i)
        header = data[i:nl].split()
        if header[-1] == b"missing":
            i = nl + 1
            continue
        size = int(header[2])
        out[p] = data[nl + 1:nl + 1 + size].decode("utf-8", "replace")
        i = nl + 1 + size + 1
    return out


def _py_module_index(files):
    """Map every dotted suffix of a module path to its files, so `teamboard.tasks`
    finds `lab11/src/teamboard/teamboard/tasks.py` (package root need not be the repo root)."""
    index = defaultdict(list)
    for f in files:
        if f.endswith(".py"):
            parts = f[:-3].removesuffix("/__init__").split("/")
            for i in range(len(parts)):
                index[".".join(parts[i:])].append(f)
    return index


def _closest(candidates, importer):
    """Pick the candidate sharing the longest directory prefix with the importer."""
    def shared(c):
        n = 0
        for a, b in zip(PurePosixPath(c).parts, PurePosixPath(importer).parts):
            if a != b:
                break
            n += 1
        return n
    return max(candidates, key=shared)


def _resolve_py(mod, names, importer, index):
    if mod.startswith("."):
        dots = len(mod) - len(mod.lstrip("."))
        pkg = PurePosixPath(importer).parent.parts
        pkg = pkg[:len(pkg) - (dots - 1)] if dots > 1 else pkg
        mod = ".".join([*pkg, mod.lstrip(".")]).strip(".")
    hits = [_closest(index[f"{mod}.{n}"], importer) for n in names if f"{mod}.{n}" in index]
    if hits:  # `from pkg import module`
        return hits
    while mod:
        if mod in index:
            return [_closest(index[mod], importer)]
        mod = mod.rpartition(".")[0]
    return []


def import_graph(repo, files, commit="HEAD", max_files=5000):
    """{file: set(files it imports)} for Python and JS/TS sources in the repo."""
    sources = [f for f in files if f.endswith(SOURCE_EXTS)][:max_files]
    contents = read_blobs(repo, commit, sources)
    file_set, py_index = set(files), _py_module_index(files)
    graph = defaultdict(set)
    for path, text in contents.items():
        if path.endswith(".py"):
            for m_from, names, m_import in PY_IMPORT.findall(text):
                name_list = [n.strip() for n in names.split(",") if n.strip()]
                graph[path].update(_resolve_py(m_from or m_import, name_list, path, py_index))
        else:
            base = PurePosixPath(path).parent
            for rel in JS_IMPORT.findall(text):
                target = PurePosixPath(*_normalize((base / rel).parts))
                for ext in JS_EXTS:
                    if f"{target}{ext}" in file_set:
                        graph[path].add(f"{target}{ext}")
                        break
        graph[path].discard(path)
    return graph


def _normalize(parts):
    out = []
    for p in parts:
        if p == "..":
            if out:
                out.pop()
        elif p != ".":
            out.append(p)
    return out

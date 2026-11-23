"""Combine the AI prediction with git facts into a ranked impact report."""
from dataclasses import dataclass, field

from . import repo_scan, safety
from .predictor import predict

RISK_ORDER = {"high": 0, "medium": 1, "low": 2}
MAX_DEPENDENTS = 20


@dataclass
class ImpactRow:
    path: str
    kind: str            # "predicted" or "imports a predicted file"
    reason: str
    confidence: float
    source: str          # "ai", "mock", "keyword", or "import graph"
    owners: list         # from CODEOWNERS
    recent: list         # [(author, commits)] other people, last N days
    branches: list       # [(branch, author)] other people's unmerged branches touching this file
    risk: str = "low"


@dataclass
class Report:
    rows: list
    branches: list       # all in-flight Branch objects (other people)
    import_edges: list   # [(importer, imported)] among shown files
    source: str
    warnings: list = field(default_factory=list)


def analyze(repo, description, me="", base=None, days=90, predictor=predict, prs=()):
    """`prs`: open PRs from github.prepare(); their refs are named pr/<number>."""
    base = base or repo_scan.default_base(repo)
    files = repo_scan.list_files(repo)
    readme_path = next((f for f in files if f.lower() == "readme.md"), None)
    readme, context_warnings = safety.read_for_llm(repo, readme_path) if readme_path else ("", [])

    result = predictor(description, files, readme=readme)
    graph = repo_scan.import_graph(repo, files)
    authors = repo_scan.recent_authors(repo, days)
    rules = repo_scan.read_codeowners(repo)
    pr_login = {f"pr/{p['number']}": p["login"] for p in prs}
    branches = repo_scan.in_flight_branches(repo, base)
    for b in branches:
        b.author = pr_login.get(b.name, b.author)
    branches = [b for b in branches if b.author != me]

    touching = {}
    for b in branches:
        for f in b.files:
            touching.setdefault(f, []).append((b.name, b.author))

    rows = {p.path: ImpactRow(p.path, "predicted", p.reason, p.confidence, p.source, [], [], [])
            for p in result.files}
    # Files that import a predicted file may break even though they are different files.
    predicted = set(rows)
    for importer, imported in sorted(graph.items()):
        for target in sorted(imported & predicted):
            if importer not in rows and sum(r.kind != "predicted" for r in rows.values()) < MAX_DEPENDENTS:
                parent = rows[target]
                rows[importer] = ImpactRow(importer, "imports a predicted file", f"imports {target}",
                                           round(parent.confidence * 0.5, 2), "import graph", [], [], [])

    for row in rows.values():
        row.owners = repo_scan.owners_for(rules, row.path)
        row.recent = [(a, n) for a, n in authors[row.path].most_common() if a != me][:3]
        row.branches = touching.get(row.path, [])
        if row.branches:
            row.risk = "high" if row.kind == "predicted" else "medium"
        elif row.recent or row.owners:
            row.risk = "medium" if row.kind == "predicted" else "low"

    ordered = sorted(rows.values(), key=lambda r: (RISK_ORDER[r.risk], -r.confidence, r.path))
    edges = [(a, b) for a in rows for b in graph.get(a, ()) if b in rows]
    return Report(ordered, branches, edges, result.source, context_warnings + result.warnings)

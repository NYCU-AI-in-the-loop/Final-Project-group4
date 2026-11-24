"""Repository docs for the LLM: what the project is and how it is laid out.

Reads README / AGENTS.md / CLAUDE.md / ARCHITECTURE.md / CONTRIBUTING.md at the repository
root and one directory down (monorepos keep the useful docs in `backend/README.md`,
`frontend/README.md`...); hidden directories and vendor/node_modules/build are skipped.
Every file goes through `safety.read_for_llm`, so secrets files are skipped and key-like
strings are hidden. Badges, images and link URLs are removed to save tokens, `<docs>` tags
are removed so a doc cannot break out of the block the predictor wraps it in, and the total
is capped so a repo with many docs cannot crowd out the file list.
"""
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from . import safety
from .predictor import SKIP

# Most useful first: agent/architecture notes describe the code layout, READMEs the project,
# CONTRIBUTING mostly the process (so it comes after every other doc, see `find_docs`).
DOC_NAMES = ("agents.md", "claude.md", "architecture.md",
             "readme.md", "readme.rst", "readme.txt", "readme", "contributing.md")
MAX_DOC_CHARS = 4000
MAX_TOTAL_CHARS = 12000
TRUNCATED = "\n[... truncated]"


@dataclass
class DocContext:
    text: str                                   # what is sent to the LLM ("" if no docs)
    used: list = field(default_factory=list)    # doc paths included, in order
    skipped: list = field(default_factory=list)  # docs left out because of MAX_TOTAL_CHARS
    warnings: list = field(default_factory=list)


def find_docs(files):
    """Doc files at the root and one directory down, most useful first."""
    rank = {name: i for i, name in enumerate(DOC_NAMES)}
    docs = []
    for f in files:
        parts = f.split("/")
        if (parts[-1].lower() in rank and len(parts) <= 2 and not parts[0].startswith(".")
                and not SKIP.search(f)):  # vendor/, node_modules/... are other people's docs
            docs.append(f)

    def key(f):
        p = PurePosixPath(f)
        name = p.name.lower()
        return (name == "contributing.md", len(p.parts), str(p.parent), rank[name])
    return sorted(docs, key=key)


BADGE_LINE = re.compile(r"^\s*(\[?!\[[^\]]*\]\([^)]*\)\]?(\([^)]*\))?\s*)+$", re.M)  # [![x](img)](url) ...
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
HTML_IMG = re.compile(r"<img\b[^>]*>", re.I)
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")   # [text](url) -> text


def clean(text):
    """Drop what helps a human reader but not file prediction: badges, images, link URLs."""
    text = HTML_COMMENT.sub("", text)
    text = BADGE_LINE.sub("", text)
    text = HTML_IMG.sub("", text)
    text = IMAGE.sub("", text)
    text = LINK.sub(r"\1", text)
    # The predictor wraps docs in <docs>...</docs>; a doc must not be able to close that early.
    text = re.sub(r"<\s*/?\s*docs\b[^>]*>", "", text, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build(repo, files, commit="HEAD"):
    """Collect the repository's docs into one text block within MAX_TOTAL_CHARS."""
    blocks, used, warnings, skipped, total = [], [], [], [], 0
    for path in find_docs(files):
        text, w = safety.read_for_llm(repo, path, commit)
        warnings += w
        text = clean(text)
        if not text:
            continue
        if len(text) > MAX_DOC_CHARS:
            text = text[:MAX_DOC_CHARS] + TRUNCATED
        block = f"### {path}\n{text}"
        if total + len(block) > MAX_TOTAL_CHARS:
            skipped.append(path)
            continue
        blocks.append(block)
        used.append(path)
        total += len(block)
    # Leaving out a low-priority doc (usually CONTRIBUTING.md) is normal, so it is not a warning.
    return DocContext("\n\n".join(blocks), used, skipped, warnings)

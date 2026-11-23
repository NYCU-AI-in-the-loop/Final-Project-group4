"""Turn a GitHub URL into a local clone whose open PRs are visible as refs/remotes/pr/<n>.

Teammates' in-flight work on GitHub mostly lives in PRs (often from forks), not in
branches of the repo itself, so we fetch each open PR's head as a remote ref.
"""
import json
import os
import re
import urllib.request
from pathlib import Path

from .repo_scan import git

URL_RE = re.compile(r"^(?:https?://)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")
CACHE_DIR = Path(__file__).resolve().parent.parent / "repos"


def parse_url(text):
    m = URL_RE.match(text.strip())
    return (m.group(1), m.group(2)) if m else None


def open_prs(owner, name):
    req = urllib.request.Request(f"https://api.github.com/repos/{owner}/{name}/pulls?state=open&per_page=100",
                                 headers={"Accept": "application/vnd.github+json"})
    if os.getenv("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return [{"number": p["number"], "title": p["title"], "login": p["user"]["login"]}
                for p in json.load(resp)]


def prepare(url, cache_dir=CACHE_DIR):
    """Clone or update the repo and fetch open PR heads. Returns (path, prs, warnings)."""
    owner, name = parse_url(url)
    path = Path(cache_dir) / f"{owner}__{name}"
    if path.exists():
        git(path, "fetch", "--quiet", "origin")
        git(path, "merge", "--quiet", "--ff-only", "@{upstream}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        git(path.parent, "clone", "--quiet", f"https://github.com/{owner}/{name}.git", path.name)

    # Drop PR refs from a previous run: those PRs may be closed now.
    for ref in git(path, "for-each-ref", "--format=%(refname)", "refs/remotes/pr").split():
        git(path, "update-ref", "-d", ref)

    warnings = []
    try:
        prs = open_prs(owner, name)
    except Exception as e:
        prs = []
        warnings.append(f"Could not list open PRs from GitHub ({e}); only branches are checked. "
                        "Setting GITHUB_TOKEN in .env avoids rate limits.")
    if prs:
        git(path, "fetch", "--quiet", "origin",
            *[f"+refs/pull/{p['number']}/head:refs/remotes/pr/{p['number']}" for p in prs])
    return path, prs, warnings

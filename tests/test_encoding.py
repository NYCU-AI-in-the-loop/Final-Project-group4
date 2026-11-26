"""Git output is read as UTF-8 whatever the OS locale or the user's git config says (issue #21).

Most checks run in a child Python with UTF-8 mode off and the C locale (on Windows: the ANSI code
page, e.g. cp950), because on a UTF-8 machine they would pass even without the fix.
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from impactmap import repo_scan

from test_analyze import run

ROOT = Path(__file__).resolve().parent.parent
NON_UTF8 = {"PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "LC_ALL": "C"}
FILES = ["CODEOWNERS", "app.py", "文件/README.md", "登入.py"]


def child(*args, **env):
    return subprocess.run([sys.executable, *args], capture_output=True, cwd=ROOT,
                          env={**os.environ, **NON_UTF8, **env})


def evaluate(expr, repo):
    """Value of `expr` (ASCII source, literal result) computed in the child process."""
    r = child("-c", f"import sys; from impactmap import repo_scan; repo = sys.argv[1]; print(ascii({expr}))", str(repo))
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    return ast.literal_eval(r.stdout.decode("ascii"))


def put(repo, path, text):
    p = repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    run(tmp_path, "init", "-b", "main")
    put(tmp_path, "app.py", "from 登入 import login\n")
    put(tmp_path, "登入.py", "def login(): pass\n")
    put(tmp_path, "文件/README.md", "說明\n")
    put(tmp_path, "CODEOWNERS", "# 擁有者\n/登入.py @login-team\n")
    run(tmp_path, "add", ".")
    run(tmp_path, "commit", "-m", "初始", author="何錦鵬")
    run(tmp_path, "switch", "-c", "jose-login")
    put(tmp_path, "app.py", "from 登入 import login  # 2\n")
    put(tmp_path, "登入.py", "def login(): return 1\n")
    run(tmp_path, "commit", "-am", "修改", author="José")
    run(tmp_path, "switch", "main")
    return tmp_path


def test_authors_and_paths(repo):
    assert evaluate("repo_scan.list_files(repo)", repo) == FILES
    assert evaluate("{p: dict(c) for p, c in repo_scan.recent_authors(repo).items()}", repo) == {
        p: {"何錦鵬": 1} for p in FILES}


def test_branches_codeowners_and_imports(repo):
    assert evaluate("[(b.name, b.author, b.files) for b in repo_scan.in_flight_branches(repo, 'main')]", repo) == [
        ("jose-login", "José", ["app.py", "登入.py"])]
    assert evaluate("repo_scan.read_codeowners(repo)", repo) == [("/登入.py", ["@login-team"])]
    assert evaluate("repo_scan.import_graph(repo, repo_scan.list_files(repo))['app.py']", repo) == {"登入.py"}


def test_non_ascii_branch_name(repo):
    run(repo, "branch", "-m", "jose-login", "feat/登入")
    assert [b.name for b in repo_scan.in_flight_branches(repo, "main")] == ["feat/登入"]


def test_git_error_is_still_a_runtime_error(repo):
    # git repeats the non-ASCII name it could not find on stderr.
    with pytest.raises(RuntimeError, match="沒有"):
        repo_scan.git(repo, "show", "HEAD:沒有.py")


def test_git_config_cannot_change_the_output_encoding(repo):
    run(repo, "config", "i18n.logOutputEncoding", "big5")
    assert evaluate("list(repo_scan.recent_authors(repo)['app.py'])", repo) == ["何錦鵬"]


def test_undecodable_bytes_do_not_crash(repo):
    # A Latin-1 author name in a commit that does not say so.
    raw = subprocess.run(["git", "-C", str(repo), "cat-file", "commit", "HEAD"], capture_output=True, check=True).stdout
    sha = subprocess.run(["git", "-C", str(repo), "hash-object", "-t", "commit", "-w", "--stdin"],
                         input=raw.replace("何錦鵬".encode(), b"Jos\xe9"), capture_output=True, check=True).stdout
    run(repo, "update-ref", "refs/heads/main", sha.decode().strip())
    assert evaluate("list(repo_scan.recent_authors(repo)['app.py'])", repo) == ["Jos�"]


def test_cli_prints_names_the_output_encoding_lacks(repo):
    # `python -m impactmap.cli ... > out.txt` on a cp950 Windows; cp950 has no "é".
    r = child("-m", "impactmap.cli", "change app startup", "--repo", str(repo), "--base", "main",
              PYTHONIOENCODING="cp950", IMPACTMAP_MOCK="1", IMPACTMAP_MOCK_DELAY="0")
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert b"in-flight: jose-login (Jos?)" in r.stdout

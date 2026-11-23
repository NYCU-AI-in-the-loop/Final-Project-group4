import json
import subprocess
from types import SimpleNamespace

import pytest

from impactmap import repo_scan
from impactmap.analyze import analyze
from impactmap.predictor import OffTopic, predict


def run(repo, *args, author="alice"):
    env = {"GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": f"{author}@x", "GIT_COMMITTER_NAME": author,
           "GIT_COMMITTER_EMAIL": f"{author}@x", "PATH": "/usr/bin:/bin:/opt/homebrew/bin"}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def write(repo, path, text):
    p = repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture
def repo(tmp_path):
    run(tmp_path, "init", "-b", "main")
    write(tmp_path, "api/auth.py", "def login(): pass\n")
    write(tmp_path, "api/users.py", "from api.auth import login\n")
    write(tmp_path, "web/src/Login.tsx", "import { login } from './client'\n")
    write(tmp_path, "web/src/client.ts", "export const login = 1\n")
    write(tmp_path, "README.md", "demo\n")
    write(tmp_path, ".github/CODEOWNERS", "/web/ @frontend-team\n")
    run(tmp_path, "add", ".")
    run(tmp_path, "commit", "-m", "init")
    # bob works on auth in an unmerged branch
    run(tmp_path, "switch", "-c", "bob-auth")
    write(tmp_path, "api/auth.py", "def login(): return 1\n")
    run(tmp_path, "commit", "-am", "auth", author="bob")
    # carol's branch is already merged -> must not be reported
    run(tmp_path, "switch", "main")
    run(tmp_path, "switch", "-c", "carol-done")
    write(tmp_path, "README.md", "demo 2\n")
    run(tmp_path, "commit", "-am", "docs", author="carol")
    run(tmp_path, "switch", "main")
    run(tmp_path, "merge", "--ff-only", "carol-done")
    return tmp_path


def fake_client(payload):
    msg = SimpleNamespace(content=json.dumps(payload))
    create = lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=msg)])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_in_flight_skips_merged_branches(repo):
    branches = repo_scan.in_flight_branches(repo, "main")
    assert [(b.name, b.author, b.files) for b in branches] == [("bob-auth", "bob", ["api/auth.py"])]


def test_import_graph_python_and_ts(repo):
    g = repo_scan.import_graph(repo, repo_scan.list_files(repo))
    assert g["api/users.py"] == {"api/auth.py"}
    assert g["web/src/Login.tsx"] == {"web/src/client.ts"}


def test_codeowners():
    rules = [("/web/", ["@fe"]), ("*.py", ["@py"])]
    assert repo_scan.owners_for(rules, "web/src/a.ts") == ["@fe"]
    assert repo_scan.owners_for(rules, "api/x.py") == ["@py"]
    assert repo_scan.owners_for(rules, "docs/web/a.md") == []


def test_analyze_flags_conflict_and_dependent(repo):
    client = fake_client({"off_topic": False, "files": [
        {"path": "api/auth.py", "reason": "login logic", "confidence": 0.9},
        {"path": "api/ghost.py", "reason": "made up", "confidence": 0.5}]})
    report = analyze(repo, "Add password reset to login", me="alice",
                     predictor=lambda d, f, readme="": predict(d, f, readme, client=client))
    rows = {r.path: r for r in report.rows}
    assert rows["api/auth.py"].risk == "high"
    assert rows["api/auth.py"].branches == [("bob-auth", "bob")]
    assert rows["api/users.py"].kind == "imports a predicted file"
    assert "api/ghost.py" not in rows
    assert any("do not exist" in w for w in report.warnings)
    assert report.rows[0].path == "api/auth.py"


def test_llm_failure_falls_back_to_keywords(repo):
    def boom(**kw):
        raise ConnectionError("no network")
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=boom)))
    result = predict("change the auth login flow", repo_scan.list_files(repo), client=client)
    assert result.source == "keyword"
    assert result.files[0].path == "api/auth.py"
    assert "unavailable" in result.warnings[0]


def test_bad_input():
    with pytest.raises(ValueError):
        predict("  ", ["a.py"])
    with pytest.raises(OffTopic):
        predict("what is the weather today", ["a.py"], client=fake_client({"off_topic": True, "files": []}))


def test_nested_package_root(tmp_path):
    run(tmp_path, "init", "-b", "main")
    write(tmp_path, "lab/src/board/board/tasks.py", "x = 1\n")
    write(tmp_path, "lab/src/board/board/cli.py", "from board import tasks\n")
    write(tmp_path, "lab/src/board/board/report.py", "from board.tasks import x\n")
    run(tmp_path, "add", ".")
    run(tmp_path, "commit", "-m", "init")
    g = repo_scan.import_graph(tmp_path, repo_scan.list_files(tmp_path))
    assert g["lab/src/board/board/cli.py"] == {"lab/src/board/board/tasks.py"}
    assert g["lab/src/board/board/report.py"] == {"lab/src/board/board/tasks.py"}


def test_file_without_recent_commits(repo):
    client = fake_client({"off_topic": False, "files": [{"path": "api/auth.py", "reason": "x", "confidence": 0.9}]})
    report = analyze(repo, "Add password reset to login", me="alice", days=0,
                     predictor=lambda d, f, readme="": predict(d, f, readme, client=client))
    assert report.rows[0].recent == []

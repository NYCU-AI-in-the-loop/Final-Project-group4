import pytest

from impactmap import safety
from impactmap.analyze import analyze

from test_analyze import fake_client, repo, run, write  # noqa: F401  (repo is a fixture)
from impactmap.predictor import predict

# Fake secrets are assembled at runtime so this file never contains a real-looking key
# (GitHub push protection would block it, and scanners would flag it).
OPENAI_KEY = "sk-" + "proj-" + "A1b2C3d4" * 5
GITHUB_TOKEN = "ghp" + "_" + "x9Y8z7W6" * 5
AWS_KEY = "AKIA" + "ABCDEFGHIJ234567"
PRIVATE_KEY = ("-----BEGIN RSA PRIVATE" + " KEY-----\nMIIEow" + "Q" * 40
               + "\n-----END RSA PRIVATE" + " KEY-----")


@pytest.mark.parametrize("path", [
    ".env", ".envrc", "backend/.env", ".env.local", ".env.production", "deploy/prod.env",
    "certs/server.pem", "tls.key", "id_rsa", "home/.ssh/id_ed25519", ".npmrc",
    "config/credentials.json", "secrets.yaml", "infra/terraform.tfvars", "Store.P12",
])
def test_sensitive_paths(path):
    assert safety.is_sensitive(path)


@pytest.mark.parametrize("path", [
    ".env.example", "backend/.env.sample", ".env.template", "README.md", "app/core/config.py",
    "keyboard.py", "docs/environment.md", "src/keys.ts", "tests/test_secrets.py",
])
def test_normal_paths(path):
    assert not safety.is_sensitive(path)


@pytest.mark.parametrize("secret", [OPENAI_KEY, GITHUB_TOKEN, AWS_KEY, PRIVATE_KEY])
def test_redact_known_key_formats(secret):
    text, n = safety.redact(f"Setup:\nuse {secret} here\nthen run it")
    assert secret not in text
    assert safety.PLACEHOLDER in text and n == 1
    assert text.startswith("Setup:") and text.endswith("then run it")


def test_redact_assignment_keeps_the_name():
    text, n = safety.redact('API_KEY=abcdef123456\npassword: "hunter2hunter2"\nDEBUG=true\n')
    assert text == f'API_KEY={safety.PLACEHOLDER}\npassword: "{safety.PLACEHOLDER}"\nDEBUG=true\n'
    assert n == 2


def test_redact_assignment_with_comment():
    assert safety.redact("export DB_PASSWORD=supersecret1  # local only") == (
        f"export DB_PASSWORD={safety.PLACEHOLDER}  # local only", 1)


def test_redact_leaves_placeholders_and_code_alone():
    text = ("OPENAI_API_KEY=sk-...\ndef check_password(password: str) -> bool:\n    return True\n"
            "password_hash = get_password_hash(password)\ntoken = create_access_token(user.id)\n"
            "SECRET_KEY: str = secrets.token_urlsafe(32)\n"
            "db_user.hashed_password = updated_password_hash\n"
            'PasswordInput.displayName = "PasswordInput"\n')
    assert safety.redact(text) == (text, 0)


def test_sensitive_file_is_not_read(tmp_path):
    # No git repo at tmp_path: reading would raise, so this proves the file is never opened.
    text, warnings = safety.read_for_llm(tmp_path, ".env")
    assert text == "" and "not sent" in warnings[0]


def test_readme_secret_is_hidden_from_the_llm(repo):  # noqa: F811
    write(repo, "README.md", f"demo\nexport OPENAI_API_KEY={OPENAI_KEY}\n")
    run(repo, "commit", "-am", "oops, committed a key")
    seen = {}

    def spy(description, files, readme=""):
        seen["readme"] = readme
        client = fake_client({"off_topic": False, "files": [
            {"path": "api/auth.py", "reason": "x", "confidence": 0.9}]})
        return predict(description, files, readme, client=client)

    report = analyze(repo, "Add password reset to login", me="alice", predictor=spy)
    assert OPENAI_KEY not in seen["readme"] and "demo" in seen["readme"]
    assert any("secret-looking" in w for w in report.warnings)

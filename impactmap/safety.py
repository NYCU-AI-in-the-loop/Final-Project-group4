"""Keep secrets out of anything we send to the LLM.

Two checks, used before any file *content* leaves the machine:
- `is_sensitive(path)`: files we never read for the LLM (.env, private keys, credentials...).
  Templates such as `.env.example` are allowed: they document settings without real values.
- `redact(text)`: replace secret-looking strings (API keys, tokens, private key blocks,
  `PASSWORD=...` lines) with a placeholder, in case a secret was committed to a normal file.

File *paths* are not secret and are still sent; only contents go through these checks.
Content is read from git (a commit), never from the working tree, so untracked files such
as a local `.env` are not visible to begin with.
"""
import re
from pathlib import PurePosixPath

from .repo_scan import read_blobs

PLACEHOLDER = "[REDACTED]"

# Exact file names (any directory), compared lowercase.
SENSITIVE_NAMES = {
    ".env", ".envrc", ".netrc", ".npmrc", ".pypirc", ".pgpass", ".htpasswd", ".git-credentials",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "credentials", "credentials.json", "secrets.json", "secrets.yaml", "secrets.yml", "secrets.toml",
    "service-account.json", "service_account.json", "terraform.tfvars", "terraform.tfstate",
}
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx", ".tfstate")
# `.env.local`, `.env.production`, `prod.env` ... but not the templates below.
ENV_FILE = re.compile(r"^\.env(\..+)?$|\.env$")
TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S),
    re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"),           # OpenAI / Anthropic
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),  # GitHub
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),                    # AWS access key id
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),                       # Google API key
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),                 # Slack
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
]
# `API_KEY=abc...`, `password: "abc..."`: keep the name, hide the value (8+ chars).
# The value must be one literal that ends the line (a trailing # comment is fine), so code
# such as `password_hash = get_password_hash(password)` is left alone. Dotted names
# (`user.hashed_password = ...`) are object attributes in code, not settings, so they are skipped.
ASSIGNMENT = re.compile(
    r"""(?im)^(\s*(?:export\s+)?[\w-]*(?:secret|password|passwd|token|api[_-]?key|private[_-]?key)[\w-]*"""
    r"""\s*[:=]\s*)(["']?)([^\s"'(){}\[\],;]{8,})\2(?=[ \t]*(?:#.*)?$)""")


def is_sensitive(path):
    """True if the file's content must never be sent to the LLM."""
    name = PurePosixPath(path).name.lower()
    if name.endswith(TEMPLATE_SUFFIXES):
        return False
    return (name in SENSITIVE_NAMES or name.endswith(SENSITIVE_SUFFIXES)
            or bool(ENV_FILE.search(name)))


def redact(text):
    """Return (text with secret-looking strings replaced, number of replacements)."""
    total = 0
    for pattern in SECRET_PATTERNS:
        text, n = pattern.subn(PLACEHOLDER, text)
        total += n
    text, n = ASSIGNMENT.subn(lambda m: f"{m.group(1)}{m.group(2)}{PLACEHOLDER}{m.group(2)}", text)
    return text, total + n


def read_for_llm(repo, path, commit="HEAD"):
    """Read a file at `commit` so it can be sent to the LLM.

    Returns (text, warnings). Sensitive files give ("", [reason]) without being read.
    """
    if is_sensitive(path):
        return "", [f"Skipped {path}: looks like a secrets file, its content is not sent to the AI."]
    # read_blobs decodes as UTF-8 whatever the OS locale is (cp950 on many Windows setups).
    text, n = redact(read_blobs(repo, commit, [path]).get(path, ""))
    warnings = [f"Hid {n} secret-looking value(s) in {path} before sending it to the AI."] if n else []
    return text, warnings

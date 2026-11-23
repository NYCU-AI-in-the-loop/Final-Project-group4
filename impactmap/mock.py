"""Mock LLM: a fixed response so the results page can be seen without an OpenAI key.

Turn it on with the environment variable IMPACTMAP_MOCK=1 (shell or .env). The description
is ignored. Only the LLM step is replaced; the response goes
through the same parsing and validation as real output, and everything after it uses real
repository data. Paths are real files in the default repository
(fastapi/full-stack-fastapi-template), written as if the request were
"Add password reset by email".
"""
import json
import os
import time
from types import SimpleNamespace

WARNING = ("Mock mode (IMPACTMAP_MOCK=1): the predicted files are a fixed sample; "
           "the rest uses real repository data.")
OTHER_REPO_WARNING = "Mock data only covers the default repository."

MOCK_FILES = [
    ("backend/app/api/routes/login.py", "Password recovery and reset endpoints live here.", 0.9),
    ("backend/app/utils.py", "Builds and sends the reset email.", 0.8),
    ("backend/app/email-templates/reset_password.html", "Email template for the reset link.", 0.7),
    ("backend/app/core/security.py", "Token and password hashing helpers.", 0.6),
    ("backend/app/core/config.py", "Reset token expiry and email settings.", 0.5),
    ("frontend/src/routes/recover-password.tsx", "Page where the user requests a reset email.", 0.8),
    ("frontend/src/routes/reset-password.tsx", "Page where the user sets a new password.", 0.8),
    ("frontend/src/routes/login.tsx", 'Adds the "Forgot password?" link.', 0.5),
    ("frontend/src/client/sdk.gen.ts", "Generated API client for the new endpoints.", 0.4),
]

RESPONSE = {"off_topic": False,
            "files": [{"path": p, "reason": r, "confidence": c} for p, r, c in MOCK_FILES]}


def enabled():
    """True if IMPACTMAP_MOCK is set to 1/true/yes/on (any case)."""
    return os.getenv("IMPACTMAP_MOCK", "").strip().lower() in {"1", "true", "yes", "on"}


def _create(**kwargs):
    time.sleep(float(os.getenv("IMPACTMAP_MOCK_DELAY", "1")))  # simulate API latency
    msg = SimpleNamespace(content=json.dumps(RESPONSE))
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


# Same interface as the parts of openai.OpenAI that the predictor uses.
client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))

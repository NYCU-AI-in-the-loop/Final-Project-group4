"""The AI step: feature description -> files the change will likely modify.

If the LLM is unavailable or returns something unusable, fall back to keyword
matching on file paths and say so, so the user is never silently given non-AI output.
"""
import json
import os
import re
from dataclasses import dataclass, field

SKIP = re.compile(r"(^|/)(node_modules|dist|build|vendor|\.git)/|\.(png|jpe?g|gif|svg|ico|pdf|lock|min\.js|map)$"
                  r"|(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|uv\.lock)$")
MAX_PATHS = 2000
MAX_FILES = 15

SYSTEM_PROMPT = f"""You help a developer plan a change in a git repository before they write code.
Given the repository's file list and a description of the planned change, predict which EXISTING
files the change will most likely modify. Only use paths that appear in the file list.

Reply with JSON only:
{{"off_topic": false, "files": [{{"path": "...", "reason": "one short sentence", "confidence": 0.0}}]}}

- confidence is between 0 and 1.
- At most {MAX_FILES} files, most likely first.
- If the description is not a code change to this repository, reply {{"off_topic": true, "files": []}}."""

STOPWORDS = {"the", "and", "for", "add", "with", "that", "this", "new", "from", "into", "when",
             "make", "change", "update", "feature", "support", "should", "want", "page", "use"}


@dataclass
class Prediction:
    path: str
    reason: str
    confidence: float
    source: str  # "ai" or "keyword"


@dataclass
class PredictResult:
    files: list
    source: str
    warnings: list = field(default_factory=list)


def check_description(description):
    text = (description or "").strip()
    if len(text) < 5:
        raise ValueError("Please describe the change you plan in at least one sentence.")
    return text


def predict(description, files, readme="", client=None, model=None):
    description = check_description(description)
    candidates = [f for f in files if not SKIP.search(f)][:MAX_PATHS]
    try:
        return _predict_llm(description, candidates, readme, client, model)
    except OffTopic:
        raise
    except Exception as e:  # network, auth, bad JSON, missing key...
        result = predict_keywords(description, candidates)
        result.warnings.insert(0, f"AI prediction unavailable ({type(e).__name__}: {e}). "
                                  "Showing keyword matches on file paths instead.")
        return result


class OffTopic(ValueError):
    pass


def _predict_llm(description, candidates, readme, client, model):
    if client is None:
        from openai import OpenAI
        client = OpenAI()  # reads OPENAI_API_KEY
    model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    user = (f"README (truncated):\n{readme[:3000]}\n\n" if readme else "") + \
        "File list:\n" + "\n".join(candidates) + f"\n\nPlanned change:\n{description}"
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
    )
    data = json.loads(resp.choices[0].message.content)
    if data.get("off_topic"):
        raise OffTopic("This does not look like a change to this repository. "
                       "Try describing the feature or bug fix you plan to make.")
    known, preds, invented = set(candidates), [], []
    for item in data.get("files", [])[:MAX_FILES]:
        path = str(item.get("path", "")).strip().lstrip("./")
        if path in known:
            conf = min(max(float(item.get("confidence", 0.5)), 0.0), 1.0)
            preds.append(Prediction(path, str(item.get("reason", "")), conf, "ai"))
        elif path:
            invented.append(path)
    warnings = []
    if invented:
        warnings.append(f"Ignored {len(invented)} path(s) the AI suggested that do not exist: "
                        + ", ".join(invented[:5]))
    if not preds:
        raise ValueError("AI returned no usable file paths")
    return PredictResult(preds, "ai", warnings)


def predict_keywords(description, files, limit=10):
    tokens = {t for t in re.findall(r"[a-z0-9]+", description.lower())
              if len(t) >= 3 and t not in STOPWORDS}
    scored = []
    for f in files:
        hits = [t for t in tokens if t in f.lower()]
        if hits:
            scored.append((len(hits), f, hits))
    scored.sort(key=lambda s: (-s[0], s[1]))
    preds = [Prediction(f, "path contains: " + ", ".join(sorted(h)), min(n / max(len(tokens), 1), 1.0), "keyword")
             for n, f, h in scored[:limit]]
    warnings = [] if preds else ["No file paths matched the description's keywords."]
    return PredictResult(preds, "keyword", warnings)

# Final-Project-group4

## Impact Map (Group 4 prototype)

Describe a change before you code it. The AI predicts which files it touches; git shows which
teammates have unmerged branches on those files or edited them recently, including files that
*import* the predicted ones.

### Setup and run

```bash
uv venv && source .venv/bin/activate && uv pip install -r requirements.txt
cp .env.example .env              # put OPENAI_API_KEY in it (optional: OPENAI_MODEL)
streamlit run app.py              # UI
python -m impactmap.cli "Add password reset by email" [--repo URL_or_path] [--me login]   # CLI
python -m pytest -q tests         # tests
```

Default repo: https://github.com/fastapi/full-stack-fastapi-template (Python backend + TS frontend,
many open PRs from different authors). A GitHub URL is cloned into `repos/` and each **open PR**
is fetched as `pr/<number>` and treated as a teammate's in-flight work (GitHub API, no token
needed; set `GITHUB_TOKEN` in `.env` if you hit the rate limit). For a local path, run
`git fetch` there first so teammates' branches are visible.
Without a working key the tool falls back to keyword matching and says so.
Run with `IMPACTMAP_MOCK=1` (e.g. `IMPACTMAP_MOCK=1 streamlit run app.py`, or put it in `.env`) to see
the results page without an API key: the AI step returns a fixed sample, everything else uses real repository data.

### Risk levels

- high: a predicted file is changed in someone else's unmerged branch
- medium: predicted file recently edited by others / listed in CODEOWNERS, or an importing file is in someone's branch
- low: otherwise

### Code

- `impactmap/repo_scan.py`: git facts: files, recent authors, CODEOWNERS, unmerged branches, import graph (Python, JS/TS)
- `impactmap/predictor.py`: AI step (OpenAI, JSON output), keyword fallback, input checks
- `impactmap/analyze.py`: combines both into a ranked report
- `impactmap/github.py`: clone a GitHub URL and fetch open PR heads
- `app.py` Streamlit UI, `impactmap/cli.py` CLI

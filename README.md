# Final-Project-group4

## Impact Map (Group 4 prototype)

Describe a change before you code it. The AI predicts which files it touches; git shows which
teammates have unmerged branches on those files or edited them recently, including files that
*import* the predicted ones.

### Setup and run

```bash
uv venv && source .venv/bin/activate && uv pip install -r requirements.txt
# Edit the existing .env; for a new checkout only: cp .env.example .env
streamlit run app.py              # UI
python -m impactmap.cli "Add password reset by email" [--repo URL_or_path] [--me login]   # CLI
python -m pytest -q tests         # tests
```

Default repo: https://github.com/fastapi/full-stack-fastapi-template (Python backend + TS frontend,
many open PRs from different authors). A GitHub URL is cloned into `repos/` and each **open PR**
is fetched as `pr/<number>` and treated as a teammate's in-flight work (GitHub API, no token
needed; set `GITHUB_TOKEN` in `.env` if you hit the rate limit). For a local path, run
`git fetch` there first so teammates' branches are visible.
The UI requires at least one configured model API key for non-mock analysis. The CLI
retains keyword fallback when its selected provider has no key; API failures also fall
back to clearly labeled keyword matching.
Run with `IMPACTMAP_MOCK=1` (e.g. `IMPACTMAP_MOCK=1 streamlit run app.py`, or put it in `.env`) to see
the results page without an API key: the AI step returns a fixed sample, everything else uses real repository data.

### Risk levels

- high: a predicted file is changed in someone else's unmerged branch
- medium: predicted file recently edited by others / listed in CODEOWNERS, or an importing file is in someone's branch
- low: otherwise

### Code

- `impactmap/repo_scan.py`: git facts: files, recent authors, CODEOWNERS, unmerged branches, import graph (Python, JS/TS)
- `impactmap/predictor.py`: AI step (OpenAI / Claude, JSON output), keyword fallback, input checks
- `impactmap/analyze.py`: combines both into a ranked report
- `impactmap/github.py`: clone a GitHub URL and fetch open PR heads
- `impactmap/context.py`: repo docs for the AI (README/AGENTS.md/CLAUDE.md... at the root and one level down, cleaned and size-capped)
- `impactmap/safety.py`: keeps secrets out of what is sent to the AI (skips `.env`/key files, hides key-like strings)
- `impactmap/model_picker.py` / `model_picker.js`: model dropdown with individually disabled options
- `app.py` Streamlit UI, `impactmap/cli.py` CLI


### OpenAI / Claude selection

Edit `.env` at the project root (beside `app.py`). Preserve any existing keys:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-6-luna
ANTHROPIC_API_KEY=your-anthropic-api-key
ANTHROPIC_MODEL=claude-haiku-5-5
IMPACTMAP_MOCK=0
GITHUB_TOKEN=
```

Create OpenAI keys at https://platform.openai.com/api-keys and Claude keys in
https://platform.claude.com/ under API Keys. The provider you use needs API access/credits.
Fill both keys to switch between providers, or only the key for the provider you use.
`GITHUB_TOKEN` is optional for public-repository PR API requests; Git clone credentials
are configured separately. Never commit `.env` (already gitignored).

The UI requires Streamlit 1.67 or newer, including its v2 custom-component API for
the model dropdown. Install dependencies with `uv pip install -r requirements.txt`, then restart
`streamlit run app.py` after editing `.env`. Existing shell environment variables take
precedence over `.env`; update/unset those if settings appear unchanged.

Select **Model** next to **Analyze**. Selection alone makes no API request. Analyze
uses that selection, and results retain the provider/model that produced them.
`AI_PROVIDER` sets the preferred initial selection. If that provider has no key, the UI
initially selects the other configured provider. Invalid or blank `AI_PROVIDER` values
show a warning and default to OpenAI, subject to the same key-availability check.
The selected provider's model environment variable overrides its default.

Only one API key is required. Missing, empty, and whitespace-only values count as unset;
keys can come from `.env` or the shell environment. The UI behaves as follows:

| Configured keys | Model dropdown | Analyze |
| --- | --- | --- |
| OpenAI only | OpenAI selected; `Claude (Missing API key)` disabled | Enabled |
| Claude only | Claude selected; `OpenAI (Missing API key)` disabled | Enabled |
| Both | Both selectable | Enabled |
| Neither | Both options disabled; `Missing API key` placeholder | Disabled |

When neither key is configured, a warning explains how to set either key in `.env`,
even if loading the repository fails. With one key configured, only the unavailable
option carries the missing-key notice. A configured key means a nonblank value; this
check does not verify API credentials or credits. A server-side check also prevents
analysis if the selected provider's key is missing at submission time.

CLI options override environment settings:

```bash
python -m impactmap.cli "Add password reset" --provider claude
python -m impactmap.cli "Add password reset" --provider openai --model gpt-6-luna
```

`IMPACTMAP_MOCK=1` disables the model selector and uses fixed sample predictions;
it keeps Analyze enabled even without keys, hides missing-key notices, and makes no model API calls. Set it to `0` for real AI. Git/PR conflict analysis,
CODEOWNERS, recent editors, dependencies, tables and graphs work with either provider.

Requests have a 60,000-character input ceiling, 4,096 output-token limit, 45-second
SDK timeout and at most one SDK retry. Claude uses low adaptive reasoning; the default
OpenAI model uses no reasoning. Truncated/invalid responses and API failures fall back
to clearly labeled keyword matching, never to another provider or more expensive model.
Model availability depends on your account. Automated tests use simulated API responses and do not incur API charges.

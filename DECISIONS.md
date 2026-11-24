# Decisions Log

## 2026-09-21 — Initial code steward
**What:** vv-chang is the initial code steward for the team.
**Why:** has experience coordinating tasks and keeping track of team progress.

## 2026-11-23 — Prototype stack: Python, Streamlit, OpenAI
**What:** The first prototype ("Impact Map") is a Python package (`impactmap/`) with a Streamlit UI (`app.py`) and a CLI. The AI step calls the OpenAI API (key in `.env`, model configurable with `OPENAI_MODEL`, default `gpt-4o-mini`) and must return JSON.
**Why:** Fastest way to get the main task running end to end for the Week 12 cross-team review; reviewers can use a web page without setup beyond `pip install`. Prompt log: Prompt.md (2026-11-23).

## 2026-11-23 — AI suggests, git facts decide the warnings; never block
**What:** The LLM only predicts which files a planned change will touch (with a reason and confidence). Who is affected comes from git: other people's unmerged branches/open PRs, recent authors (90 days), CODEOWNERS, plus files that import a predicted file (one hop). Paths the LLM invents are dropped and reported. If the LLM fails, we fall back to keyword matching on paths and label it "not AI"; empty or off-topic input is rejected with a message.
**Why:** Follows our CP1 human-AI boundary (AI flags, humans decide) and interview findings: warnings must name affected teammates and must not slow down parallel work. One-hop imports cover "different files, same module", which GitHub's conflict detection misses.

## 2026-11-23 — Open PRs count as in-flight work; default demo repo
**What:** When given a GitHub URL, the tool clones it into `repos/` (gitignored) and fetches every open PR head as `pr/<number>`, attributed to the PR author's GitHub login. Default repo: https://github.com/fastapi/full-stack-fastapi-template.
**Why:** On GitHub most teammates' work lives in PRs from forks, not in branches of the repo. The template has a Python backend and TS frontend (matches our back-end/front-end scenario) and had 12 open PRs from 10 authors on 2026-11-23; pallets/flask had only 3 open PRs from 2 authors.

## 2026-11-23 — Mock LLM mode via `IMPACTMAP_MOCK=1`
**What:** The env variable replaces only the AI step with a fixed sample; everything else uses real repo data. Off by default, so normal behavior is unchanged.
**Why:** Lets people without an OpenAI key see the results page. Typing `mock = true` felt odd and Streamlit rejects `--mock`, so we used an env variable.

## 2026-11-23 — Filter secrets before repo content goes to the LLM
**What:** `impactmap/safety.py` skips secrets files (`.env*`, keys, credentials; `.env.example` allowed) and replaces key-like strings with `[REDACTED]` before content is sent to the AI. Paths are not filtered.
**Why:** We are starting to send file contents, and people do commit secrets (the demo repo commits `.env`). Rejected: an external scanner (extra dependency). Led by bbbguji.

## 2026-11-24 — Settings under the title, no sidebar
**What:** The repo, name, base-branch and day-window inputs move from the sidebar to the main page, between the title caption and the description box (repo on its own row, the other three side by side).
**Why:** After an analysis, opening or closing the sidebar lagged for a long time, probably because the browser has to lay out the large results (table and graph) again at the new width. Without a sidebar there is nothing to toggle, and the settings sit next to the description, so first-time reviewers don't miss them.

## 2026-11-24 — Send root and sub-directory docs to the AI, not just the README
**What:** `impactmap/context.py` sends README/AGENTS.md/CLAUDE.md/ARCHITECTURE.md/CONTRIBUTING.md from the root and one level down, cleaned and capped (4,000 chars each, 12,000 total), inside `<docs>` marked as data, not instructions.
**Why:** Monorepos describe their layout in `backend/README.md`, `frontend/README.md`. Demo repo: 3 docs sent instead of 3,000 chars of the root README (2,731 → 4,293 input tokens). Led by bbbguji.

## 2026-11-24 — Code steward: bbbguji for PR #10
**What:** bbbguji was code steward for PR #10 (kiki, settings under the title): ran it locally in mock mode with pytest (41 passed), approved with one non-blocking suggestion (the long "Your name…" label wraps and misaligns the three inputs; shorten it and move the note into `help=`), and merged it.
**Handoff:** the label suggestion is left as a follow-up for kiki.

## 2026-11-24 — OpenAI / Claude model selection
**What:** Added a compact model-provider selector beside Analyze and `--provider` / `--model` options to the CLI. OpenAI and Claude use separate API integrations with shared prediction validation and the existing git-based impact analysis. `AI_PROVIDER` sets the default provider; `OPENAI_MODEL` and `ANTHROPIC_MODEL` configure its model. UI selection takes precedence over the default, and reports retain the provider/model that produced them. Selecting a provider alone makes no API request. Mock mode disables the selector and continues to use fixed predictions without calling either API.
**Why:** Let users choose either provider without duplicating conflict detection, ownership lookup, dependency analysis, or report rendering. Keeping the original provider/model on each report prevents a selection change from relabeling an earlier result.
**Configuration handling:** Invalid or blank `AI_PROVIDER` settings show a warning and default the UI selection to OpenAI; users can still select Claude and run analysis.
**Follow-up resolved:** The missing-key UI policy is defined in the entry below; invalid-provider handling remains a separate configuration check.


## 2026-11-24 — Show API key availability and disable unavailable models
**What:** The UI needs only one of `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. Missing, empty, and whitespace-only values are unavailable. Such providers remain visible as `(Missing API key)` but cannot be selected. Initial selection uses a configured provider when the preferred provider has no key. When neither key is present, show setup guidance before repository loading and disable Analyze. Keep a server-side missing-key guard at submission. Mock mode hides these notices, disables model selection, and allows Analyze without keys.
**Why:** Make configuration problems visible before submission while allowing users with either provider to work. This explicitly makes missing credentials a UI prerequisite; the earlier “never block” principle still applies to collaboration-risk warnings. CLI keyword fallback and API-failure fallback are unchanged.
**Implementation:** A small Streamlit v2 component (`impactmap/model_picker.py` and `.js`) renders a native select with individually disabled options. The dependency now requires Streamlit 1.67 or newer. Selection alone makes no model API request; availability checks only inspect nonblank values, not credential validity or credits.

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

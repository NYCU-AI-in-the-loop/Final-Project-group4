# Prompt Log

Every prompt that produced code, text, or a decision that ended up in the repo.
Tags: `new feature`, `main`, `summary`.

---

## 2026-11-23 — Impact Map first prototype `new feature`

**Who:** Hans
**Tool / model:** Claude Code, Claude Opus 5.5
**Related:** PR for branch `feat/impact-map`; DECISIONS.md entries dated 2026-11-23

### Prompts (in order, original wording)

1. "According to Group4_CP1.pdf and the Week 12 lab spec, discuss with me an initial implementation."
   → AI proposed a 5-step pipeline (ingest repo, find in-flight work, LLM predicts files,
   expand by imports, ranked output + failure states) and asked about stack and LLM.
2. "用python可以。LLM的api用.env，裡面有openai key。現在先做一個版本出來"
   → AI wrote `impactmap/` (repo_scan, predictor, analyze), `app.py` (Streamlit), CLI and tests.
3. "你建議可以拿哪個github repo去測試？可以用github上別人的repo。然後預設就用這個。"
   → AI compared candidates by open PRs/authors, picked fastapi/full-stack-fastapi-template,
   added `impactmap/github.py` (clone URL + fetch open PRs as `pr/<n>`) and made it the default.
4. "你覺得現在的實作怎麼樣？" → review of limitations (recorded in "Known gaps" below).
5. "幫我把現在的實作放到local repo上面" / "也更新Prompt.md, DECISIONS.md" → this entry.

### What we kept

- Overall pipeline and module split; Streamlit UI; OpenAI with JSON output; keyword fallback.
- Default demo repo fastapi/full-stack-fastapi-template.

### What changed vs. the AI's first output

- The AI first started writing code directly in this repo; we had it move to a scratch folder
  first, then copied it here on a feature branch after it ran.
- Bugs found while verifying (the AI ran tests + real runs, a human checked the output):
  - Crash when a predicted file had no commits in the last 90 days (`dict` has no `most_common`).
    Fixed + regression test.
  - Import expansion chained through several hops depending on sort order; limited to one hop.
  - Python imports in nested package roots (e.g. `lab11/src/teamboard/teamboard/tasks.py`
    imported as `teamboard.tasks`) were not resolved; now matched by module suffix + test.
  - CLI argument order was fragile; repo became a `--repo` option.

### How it was checked

- `python -m pytest -q tests`: 8 passed (temp git repos with fake teammates' branches; fake LLM client).
- Real OpenAI run on the default repo: predicted `login.py`, `deps.py`, etc. and flagged open PRs
  touching them. Streamlit UI driven headlessly (`streamlit.testing.v1.AppTest`) for empty,
  normal and off-topic input; bad API key → keyword fallback with a warning.

### Known gaps (not done yet)

- Prediction accuracy not measured (CP1 threshold: >60% precision/recall); next: replay merged PRs.
- LLM sees file paths only, not file contents.
- TS path aliases (`@/...`) not resolved: in the demo repo ~200 of ~260 frontend imports are missed.
- One-hop import expansion is noisy (e.g. `models.py` pulls in 15+ low-risk files).

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

---

## 2026-11-23 — Mock LLM mode `new feature`

**Who:** kiki · **Tool / model:** Claude Code, Claude Opus 5.5 · **Related:** DECISIONS.md 2026-11-23 (mock mode)

1. "Read SPEC-mock-llm.md to implement mock, ask me if you're not sure about some decision." (spec deleted; decision in DECISIONS.md)
   → `impactmap/mock.py`: fixed sample prediction, triggered by typing `mock = true`.
2. "I think to let the user type \"mock = true\" is a bit of strange, could I just use mock mode
   type in command? streamlit run app.py --mock?" → Streamlit rejects `--mock`, so we switched to
   the env variable `IMPACTMAP_MOCK=1` and removed the text trigger.

**Kept / changed:** kept the AI's mock module; dropped its mock tests (not worth it for a demo helper); changed the trigger (text → env variable).
**Checked:** existing 8 tests still pass; CLI with `IMPACTMAP_MOCK=1` on the default repo shows `source: mock`.

---

## 2026-11-23 — Risk highlight in Affected files table `new feature`

**Who:** kiki · Claude Code, Claude Opus 5.5 · branch `feat/affected-files-table-ui`

"修 Affected files table，我想要他在 high medium low 的 risk 能有紅、黃、綠，我不想要改變儲存格顏色，我想要他本身像是被 highlight"
→ switched to `st.table`, the only way to highlight the text itself (loses sort/search).
Checked: runs in mock mode without errors; colors not checked by eye yet.

## 2026-11-23 — Copyable file paths in Affected files table `new feature`

**Who:** kiki · Claude Code, Claude Opus 5.5 · branch `feat/affected-files-table-ui`

"the content in file column of Affected files table is too long for user, turn it into a copyable text(maybe show icon at the right side when hovering?)"
→ table drawn as HTML (`st.html`): file name + dim folder, copy icon on row hover. Streamlit strips `<svg>`, so the icon is CSS.
Checked: hover + copy tested in Chrome (light/dark) in mock mode.

---

## 2026-11-23 — Secret filter before sending repo content to the LLM `new feature`

**Who:** bbbguji · **Tool / model:** Claude Code, Claude Opus 5.5 · branch `feat/sensitive-filter` · **Related:** DECISIONS.md 2026-11-23 (filter secrets)

1. "閱讀專題要求與 repo……我負責的是『現在僅用檔名分析，應該要包含到讀檔案 repo (/root, 但要排除機敏檔案)』……仔細思考後和我討論目前做法可不可行、有哪些地方可以改進" → AI proposed a plan: root/sub-dir docs + per-directory index cached outside the target repo, keyed by git SHAs, and a secret filter first; split into several small PRs.
2. "粒度用目錄層級、LLM 摘要明確觸發、用方案B……開始著手處理PR1" → `impactmap/safety.py`, wired into the README read in `analyze.py`, `tests/test_safety.py`.
3. "DECISIONS.md再稍微精簡一點，之後再次檢查有沒衝突和錯誤後發出pr" → re-check found a bug: the `PASSWORD=...` rule also hid ordinary code (`password_hash = get_password_hash(password)`) in 19 of 252 files of the demo repo. Fixed: the value must be one literal ending the line, and dotted names (object attributes) are skipped → 0 false positives; added `.envrc`.

**Kept / changed:** kept the AI's module and tests; fake keys in tests are built by string concatenation so the repo never contains a real-looking key (push protection). Paths are not filtered, only contents.
**Checked:** 41 tests pass (8 old + 33 new). On the default repo: `.env` and `frontend/.env` are skipped, and no source/doc file has a redaction (false positives 19 → 0 after the fix). CLI in mock mode unchanged.

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

---

## 2026-11-24 — Move sidebar settings under the title `UI`

**Who:** kiki · Claude Code, Claude Opus 5.5 · branch `feat/settings-under-title` · **Related:** DECISIONS.md 2026-11-24

"want to remove side bar, and let the content in side bar move to under "Impact Map" heading."
"…there would be a long delay while opening and closing the side bar after analyses… so I think remove it would be a better choice" (reason, added to DECISIONS.md)
→ AI asked which heading (page title vs. graph subheader), layout, expander or not; agreed: page title, repo full width + 3 columns, all visible.
Checked: tests pass; app starts headless in mock mode.

---

## 2026-11-24 — Root and sub-directory docs as AI context `new feature`

**Who:** bbbguji · **Tool / model:** Claude Code, Claude Opus 5.5 · branch `feat/repo-docs-context` · **Related:** DECISIONS.md 2026-11-24 (docs context)

1. "PR已經merge了，開始做PR2。先說明之前程式是怎麼處理的，現在有修改哪一些東西、功能" → `impactmap/context.py` (find, clean, cap docs), wired into `analyze.py`; `predictor.py` drops the 3,000-char README cut and wraps docs in `<docs>`; CLI prints which docs were used; `safety.read_for_llm` now decodes as UTF-8 regardless of OS locale.
2. "再次確認pr2的內容有無錯誤" → re-check found two gaps: a doc containing `</docs>` could close the docs block early (prompt injection), and docs under `vendor/`/`node_modules/` would be sent. Fixed both + tests.

**Kept / changed:** kept the AI's module and tests. On the demo repo every run showed a yellow "doc over size limit" warning for CONTRIBUTING.md; changed to an info field (`context_skipped`), since leaving out a low-priority doc is expected.
**Checked:** 49 tests pass (41 old + 8 new). Demo repo: 4 docs found, 3 sent; input 2,731 → 4,293 tokens (gpt-4o-mini tokenizer). CLI and Streamlit (headless, mock mode) run without errors.

---

## 2026-11-24 — Cmd+Enter runs the analysis `UI`

**Who:** Hans · Claude Code, Claude Opus 5.5 · branch `fix/cmd-enter-submits`

"I found a problem where the UI hints: cmd+enter to submit, but it did not work properly. Am I misunderstanding it, or is it a real bug?"
→ AI found the hint actually says "Press ⌘+Enter to apply": outside a form it only applies the text and does not click Analyze (Streamlit 1.67 shows "submit form" only inside `st.form`). Wrapped the description box and Analyze button in a borderless `st.form`.
Checked: 49 tests pass; headless AppTest in mock mode: submitting the form renders the results with no errors.


---

## 2026-11-24 — Missing API key guidance and model availability `new feature`

**Tool / model:** Codex, GPT-6 · **Branch:** `feat/missing-api-key-warning` · **Related:** DECISIONS.md 2026-11-24 (API key availability)

### Prompts (original wording)

1. "請pull最新的main，並且重新開一個分支，我這次要實作的功能是，當沒有填寫.env時，前端要顯示miss api key等字樣"
2. "如果剛剛已經有建立新的分支，繼續修改就好"
3. "如果openai或是claude只要其中一個有就可以，miss的可以在下拉選單後面()寫出，那如果兩個都沒有，分析按鈕就要不能按"
4. "請根據這次所有的改動更新所有應該要更新的文件"

**Kept / changed:** Kept missing-key setup guidance and the submission guard. Changed the initial warning for every absent key to a warning only when both are absent; otherwise show `(Missing API key)` beside the unavailable provider. The current implementation uses a custom dropdown that disables unavailable options, selects an available provider initially, and disables Analyze when neither key is configured. Mock mode remains usable without keys. Updated README, `.env.example`, and the decision log to match, including the Streamlit 1.67 minimum and the distinction between UI prerequisites and CLI fallback.

**Validation scope:** Automated tests cover absent/empty/whitespace keys, either provider configured alone, both configured, disabled dropdown-option data, Analyze availability, setup guidance before a repository-loading failure, and mock mode. Streamlit AppTest inspects component data and simulated selection state; it does not establish browser rendering or native dropdown interaction correctness. Tests use simulated providers and do not call paid model APIs.

---

## 2026-11-26 — Git output crash on non-UTF-8 Windows (issue #21) `bug fix`

**Who:** bbbguji · **Tool / model:** Claude Code, Claude Opus 5.5 · branch `fix/git-output-encoding` · **Related:** issues #21, #14 (Group 16, finding 1); DECISIONS.md 2026-11-26 (UTF-8 git output)

1. "現在開始修這個問題一(已經發出issue了，在issue#21，之後發PR)。先說明之前程式是怎麼處理的，現在有修改哪一些東西、功能。之後請你在一次完整的檢查相關程式有無問題(確保不會再有bug)" → `git()` decodes as UTF-8 and forces git's path/log encoding; CLI no longer crashes on names the output encoding lacks; `tests/test_encoding.py`.

**Kept / changed:** kept the fix proposed in #21. The check added two things it did not list: non-ASCII paths came back as `"\347\231..."`, and with `git()` alone fixed, `python -m impactmap.cli > out.txt` crashed on "é" under cp950.
**Checked:** 77 tests pass (70 old + 7 new) with `PYTHONUTF8=0` (cp950) and `1`; 6 of the 7 new tests fail on the old code under cp950. Streamlit (headless, mock mode, cp950) crashed before and works now; demo repo results are unchanged.

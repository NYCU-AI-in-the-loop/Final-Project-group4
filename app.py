"""Streamlit UI: describe a planned change, see which files and teammates it affects."""
from html import escape
from pathlib import Path, PurePosixPath

import streamlit as st
from dotenv import load_dotenv

import os

from impactmap import github, repo_scan, mock
from impactmap.analyze import analyze
from impactmap.predictor import OffTopic, resolve_model, KEY_NAMES
from impactmap.model_picker import model_picker

load_dotenv(Path(__file__).resolve().parent / ".env")

DEFAULT_REPO = "https://github.com/fastapi/full-stack-fastapi-template"


@st.cache_data(ttl=600, show_spinner="Cloning / updating repository and fetching open PRs...")
def load_repo(text):
    """GitHub URL -> cached clone with open PRs; local path -> used as is."""
    if github.parse_url(text):
        path, prs, warnings = github.prepare(text)
        return str(path), prs, warnings
    if not Path(text).is_dir():
        raise ValueError(f"{text} is neither a GitHub URL nor a local directory")
    return text, [], []


RISK_COLOR = {"high": "#f4a6a6", "medium": "#f7d794", "low": "#d5e8d4"}
# Affected files table, drawn as HTML so the risk word looks highlighted with a marker and
# each file path gets a copy button on hover. Every value is HTML-escaped (paths, names and
# branch names come from other people's repositories).
TABLE_CSS = """
<style>
.im-wrap { overflow-x: auto; }
.im-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.im-table th, .im-table td { padding: 0.45rem 0.6rem; text-align: left; vertical-align: top;
  border-bottom: 1px solid rgba(128, 128, 128, 0.25); }
.im-table th { font-weight: 600; opacity: 0.75; white-space: nowrap; }
.im-risk { font-weight: 700; padding: 0.05rem 0.35rem; border-radius: 0.2rem; }
/* Opaque marker + darker text of the same hue, so it reads the same in light and dark theme. */
.im-risk.high { background: #ffc9c9; color: #b71c1c; }
.im-risk.medium { background: #fff3a3; color: #7a5d00; }
.im-risk.low { background: #c8f2d4; color: #146c2e; }
.im-file { display: flex; align-items: flex-start; gap: 0.4rem; min-width: 12rem; max-width: 22rem; }
.im-file-text { flex: 1; min-width: 0; }
.im-name { font-weight: 600; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.im-dir { font-size: 0.75rem; opacity: 0.6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.im-copy { visibility: hidden; flex: none; margin-left: auto; border: 0; background: none; padding: 0.1rem; cursor: pointer;
  color: inherit; opacity: 0.6; line-height: 0; }
.im-copy:hover { opacity: 1; }
.im-table tr:hover .im-copy, .im-copy:focus-visible { visibility: visible; }
.im-copy .icon { position: relative; display: inline-block; width: 14px; height: 14px; }
.im-copy .icon::before, .im-copy .icon::after { content: ""; position: absolute; border: 1.5px solid currentColor;
  border-radius: 2px; box-sizing: border-box; }
.im-copy .icon::before { left: 0; top: 0; width: 9px; height: 9px; border-right: 0; border-bottom: 0; }
.im-copy .icon::after { left: 4px; top: 4px; width: 10px; height: 10px; }
.im-copy .done { display: none; font-size: 14px; line-height: 14px; font-weight: 700; }
.im-copy.copied .icon { display: none; }
.im-copy.copied .done { display: inline; }
</style>
"""
# Plain spans drawn with CSS: Streamlit's HTML sanitizer removes <svg>.
COPY_ICON = '<span class="icon"></span><span class="done">✓</span>'
COPY_JS = """
<script>
if (!window.imCopyReady) {
  window.imCopyReady = true;
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".im-copy");
    if (!btn) return;
    const text = btn.dataset.path;
    const done = () => { btn.classList.add("copied"); setTimeout(() => btn.classList.remove("copied"), 1200); };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done);
    } else {  // e.g. opened over plain http on another machine
      const t = document.createElement("textarea");
      t.value = text; document.body.appendChild(t); t.select();
      document.execCommand("copy"); t.remove(); done();
    }
  });
}
</script>
"""


def file_cell(path):
    p = PurePosixPath(path)
    folder = f"{p.parent}/" if str(p.parent) != "." else ""
    full = escape(path)
    return (f'<div class="im-file" title="{full}"><div class="im-file-text">'
            f'<div class="im-name">{escape(p.name)}</div><div class="im-dir">{escape(folder)}</div></div>'
            f'<button class="im-copy" type="button" data-path="{full}" title="Copy path" '
            f'aria-label="Copy path {full}">{COPY_ICON}</button></div>')


def affected_table(rows):
    head = ["risk", "file", "why", "confidence", "from", "in-flight branches", "recent editors", "CODEOWNERS"]
    body = []
    for r in rows:
        cells = [
            f'<span class="im-risk {r.risk}">{r.risk}</span>',
            file_cell(r.path),
            escape(r.reason),
            f"{r.confidence:.2f}",
            escape(r.source),
            escape(", ".join(f"{b} ({a})" for b, a in r.branches)),
            escape(", ".join(f"{a} ({n})" for a, n in r.recent)),
            escape(", ".join(r.owners)),
        ]
        body.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    return (TABLE_CSS + '<div class="im-wrap"><table class="im-table"><thead><tr>'
            + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"
            + "".join(body) + "</tbody></table></div>" + COPY_JS)


def to_dot(report):
    lines = ["digraph G {", "rankdir=LR;", 'node [shape=box, style="rounded,filled", fontname="Helvetica"];']
    for r in report.rows:
        who = ", ".join(r.owners or [a for a, _ in r.recent]) or "no recent owner"
        lines.append(f'"{r.path}" [label="{r.path}\\n{who}", fillcolor="{RISK_COLOR[r.risk]}"];')
    for a, b in report.import_edges:
        lines.append(f'"{a}" -> "{b}" [style=dashed, label="imports"];')
    people = {}
    for r in report.rows:
        for branch, author in r.branches:
            people.setdefault((branch, author), []).append(r.path)
    for (branch, author), paths in people.items():
        node = f"{author}\\n({branch})"
        lines.append(f'"{node}" [shape=ellipse, fillcolor="#cfe2f3"];')
        for p in paths:
            lines.append(f'"{node}" -> "{p}" [color="#cc0000", label="editing"];')
    lines.append("}")
    return "\n".join(lines)


st.set_page_config(page_title="Impact Map", layout="wide")
st.title("Impact Map")
st.caption("Describe a change before you code it. See which files it likely touches "
           "and which teammates are working there.")

available_providers = [p for p, name in KEY_NAMES.items() if os.getenv(name, "").strip()]
if not mock.enabled():
    if not available_providers:
        st.warning(
            "Missing API key: set either `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. "
            "Set the key for the model you want to use in the project root `.env` "
            "(see `.env.example`), then restart Streamlit."
        )

repo_input = st.text_input("GitHub URL or local repository path", value=DEFAULT_REPO)
try:
    repo, prs, repo_warnings = load_repo(repo_input)
except Exception as e:
    st.error(f"Could not open repository: {e}")
    st.stop()
col_me, col_base, col_days = st.columns(3)
me = col_me.text_input("Your name or GitHub login (excluded from warnings)")
base = col_base.text_input("Base branch", value=repo_scan.default_base(repo))
days = col_days.number_input("Recent-author window (days)", 7, 365, 90)
st.caption(f"{len(prs)} open PRs loaded as in-flight work." if prs else
           "Local path: run `git fetch` there first so teammates' branches are up to date.")

# A form so that Cmd/Ctrl+Enter in the text area runs the analysis; outside a form it only
# applies the text and the button is not clicked.
with st.form("describe", border=False):
    description = st.text_area("What do you plan to change?",
                               placeholder="e.g. Add password reset by email to the login page")
    button_col, model_col = st.columns([1, 2.5], width=400, vertical_alignment="center")
    try:
        default_provider, _ = resolve_model()
    except ValueError:
        default_provider = "openai"
        st.warning("Invalid AI_PROVIDER configuration. Use openai or claude; defaulting to OpenAI.")
    if not mock.enabled() and available_providers and default_provider not in available_providers:
        default_provider = available_providers[0]
    model_labels = {"openai": "OpenAI", "claude": "Claude"}
    selectable_providers = list(KEY_NAMES) if mock.enabled() else available_providers
    selected_provider = st.session_state.get("model_picker", {}).get("provider")
    if selected_provider not in selectable_providers:
        selected_provider = default_provider if selectable_providers else None
    with model_col:
        selection = model_picker(
            key="model_picker",
            data={
                "selected": selected_provider,
                "disabled": mock.enabled(),
                "options": [
                    {"value": p,
                     "label": label + (" (Missing API key)" if p not in selectable_providers else ""),
                     "disabled": p not in selectable_providers}
                    for p, label in model_labels.items()
                ],
            },
            default={"provider": selected_provider},
            on_provider_change=lambda: None,
        )
    provider = selection.provider
    if provider not in selectable_providers:
        provider = selected_provider
    submitted = button_col.form_submit_button("Analyze", type="primary",
                                              disabled=not mock.enabled() and not available_providers)
    if mock.enabled():
        st.caption("MOCK mode: fixed sample data; no model API is called. Set IMPACTMAP_MOCK=0 to use AI.")

if submitted:
    provider, model = resolve_model(provider)
    if not mock.enabled() and not os.getenv(KEY_NAMES[provider], "").strip():
        st.error(f"Missing API key: {KEY_NAMES[provider]}. "
                 "Set it in the project root .env, then restart Streamlit.")
        st.stop()
    try:
        with st.spinner("Asking the AI and reading git history..."):
            report = analyze(repo, description, me=me, base=base, days=int(days), prs=prs, provider=provider, model=model)
    except (OffTopic, ValueError, RuntimeError) as e:
        st.error(str(e))
        st.stop()

    st.session_state["analysis_result"] = (repo_input, report, repo_warnings)

if "analysis_result" in st.session_state and st.session_state["analysis_result"][0] == repo_input:
    _, report, saved_warnings = st.session_state["analysis_result"]
    for w in saved_warnings + report.warnings:
        st.warning(w)
    label = {"ai": f"AI ({report.provider} · {report.model})", "mock": "MOCK data (AI not called)"}.get(
        report.source, "keyword matching (not AI)")
    st.info(f"Predicted files come from **{label}**. They are guesses: check them before acting.")

    high = [r for r in report.rows if r.risk == "high"]
    if high:
        st.subheader("Potential conflicts")
        for r in high:
            who = ", ".join(f"{a} on `{b}`" for b, a in r.branches)
            st.markdown(f"- `{r.path}` is also being edited by {who}. Consider talking to them before you start.")

    st.subheader("Affected files")
    st.html(affected_table(report.rows), unsafe_allow_javascript=True)

    st.subheader("Impact map")
    st.caption("Red = someone else's unmerged branch edits it; yellow = others edited it recently; "
               "dashed arrows = imports.")
    st.graphviz_chart(to_dot(report))

    with st.expander(f"All unmerged branches by others ({len(report.branches)})"):
        titles = {f"pr/{p['number']}": p["title"] for p in prs}
        for b in report.branches:
            st.markdown(f"- `{b.name}` by {b.author}: {len(b.files)} files  {titles.get(b.name, '')}")

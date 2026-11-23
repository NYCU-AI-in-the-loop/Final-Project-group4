"""Streamlit UI: describe a planned change, see which files and teammates it affects."""
from pathlib import Path

import re

import streamlit as st
from dotenv import load_dotenv

from impactmap import github, repo_scan
from impactmap.analyze import analyze
from impactmap.predictor import OffTopic

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
# Marker-pen highlight with darker text of the same color behind the risk word (Streamlit badges).
RISK_MARKER = {"high": "red", "medium": "yellow", "low": "green"}


def md(text):
    """Escape text so st.table shows it literally instead of as Markdown."""
    return re.sub(r"([\\`*_{}\[\]()<>#+\-.!|~:])", r"\\\1", str(text))


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

with st.sidebar:
    repo_input = st.text_input("GitHub URL or local repository path", value=DEFAULT_REPO)
    try:
        repo, prs, repo_warnings = load_repo(repo_input)
    except Exception as e:
        st.error(f"Could not open repository: {e}")
        st.stop()
    me = st.text_input("Your name or GitHub login (excluded from warnings)")
    base = st.text_input("Base branch", value=repo_scan.default_base(repo))
    days = st.number_input("Recent-author window (days)", 7, 365, 90)
    st.caption(f"{len(prs)} open PRs loaded as in-flight work." if prs else
               "Local path: run `git fetch` there first so teammates' branches are up to date.")

description = st.text_area("What do you plan to change?",
                           placeholder="e.g. Add password reset by email to the login page")

if st.button("Analyze", type="primary"):
    try:
        with st.spinner("Asking the AI and reading git history..."):
            report = analyze(repo, description, me=me, base=base, days=int(days), prs=prs)
    except (OffTopic, ValueError, RuntimeError) as e:
        st.error(str(e))
        st.stop()

    for w in repo_warnings + report.warnings:
        st.warning(w)
    label = {"ai": "AI (OpenAI)", "mock": "MOCK data (AI not called)"}.get(
        report.source, "keyword matching (not AI)")
    st.info(f"Predicted files come from **{label}**. They are guesses: check them before acting.")

    high = [r for r in report.rows if r.risk == "high"]
    if high:
        st.subheader("Potential conflicts")
        for r in high:
            who = ", ".join(f"{a} on `{b}`" for b, a in r.branches)
            st.markdown(f"- `{r.path}` is also being edited by {who}. Consider talking to them before you start.")

    st.subheader("Affected files")
    st.table([{
        "risk": f":{RISK_MARKER[r.risk]}-badge[**{r.risk}**]",
        "file": f"`{r.path}`",
        "why": md(r.reason),
        "confidence": f"{r.confidence:.2f}",
        "from": md(r.source),
        "in-flight branches": md(", ".join(f"{b} ({a})" for b, a in r.branches)),
        "recent editors": md(", ".join(f"{a} ({n})" for a, n in r.recent)),
        "CODEOWNERS": md(", ".join(r.owners)),
    } for r in report.rows], hide_index=True)

    st.subheader("Impact map")
    st.caption("Red = someone else's unmerged branch edits it; yellow = others edited it recently; "
               "dashed arrows = imports.")
    st.graphviz_chart(to_dot(report))

    with st.expander(f"All unmerged branches by others ({len(report.branches)})"):
        titles = {f"pr/{p['number']}": p["title"] for p in prs}
        for b in report.branches:
            st.markdown(f"- `{b.name}` by {b.author}: {len(b.files)} files  {titles.get(b.name, '')}")

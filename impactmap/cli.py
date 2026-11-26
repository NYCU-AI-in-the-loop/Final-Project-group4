"""Command-line version: python -m impactmap.cli "planned change" [--repo URL_or_path] """
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import github
from .analyze import analyze

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def main():
    # Redirected output uses the OS encoding: print "?" for a name it lacks instead of crashing.
    sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default="https://github.com/fastapi/full-stack-fastapi-template",
                    help="GitHub URL or local path")
    ap.add_argument("--me", default="")
    ap.add_argument("--base")
    ap.add_argument("--provider", choices=["openai", "claude"])
    ap.add_argument("--model", help="Override the selected provider model")
    ap.add_argument("description")
    args = ap.parse_args()
    repo, prs, warnings = args.repo, [], []
    if github.parse_url(args.repo):
        repo, prs, warnings = github.prepare(args.repo)
    report = analyze(repo, args.description, me=args.me, base=args.base, prs=prs, provider=args.provider, model=args.model)
    report.warnings[:0] = warnings
    for w in report.warnings:
        print("WARNING:", w)
    print(f"source: {report.source}; provider: {report.provider}; model: {report.model}")
    skipped = f" (left out, size limit: {', '.join(report.context_skipped)})" if report.context_skipped else ""
    print("docs sent to the AI: " + (", ".join(report.context_files) or "none") + skipped)
    for r in report.rows:
        branches = ", ".join(f"{b} ({a})" for b, a in r.branches)
        print(f"[{r.risk:6}] {r.confidence:.2f} {r.path}  -- {r.reason}"
              + (f"  | in-flight: {branches}" if branches else ""))


if __name__ == "__main__":
    main()

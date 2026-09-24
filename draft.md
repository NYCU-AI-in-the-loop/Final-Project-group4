# Week 3 Lab
## Part 2 — Draft AI Usage Guidelines
### Section 1

We will use Claude Code to generate an initial test skeleton for a new module, first-draft docstrings, API documentation, and test cases — a human always reviews the generated code and confirms it meets our coding standards before it's merged.

## Section 2

Prompt log (Prompt.md) — every prompt that produces code, text, or a decision that ends up in the repo gets logged (prompt, model, what we kept vs. changed); one-off debugging or syntax questions don't need an entry. Entries are tagged as new feature, main, or summary.

DECISIONS.md — logs the reasoning, not a transcript. An entry goes here whenever a change is large enough to affect our approach, or an AI suggestion changes what actually ends up in the repo.

PR description — always names whether AI was involved, in one sentence, and links to the relevant log entry.

AGENTS.md — separate from the above; documents new reusable prompting techniques/skills the team develops.



## Section 3 — How we will handle disagreements about AI output quality

- **Rejections should include a reason**
  - Reviewers briefly explain why the output is rejected, such as incorrect behavior, poor maintainability, or inconsistency with the project design.

- **Discuss disagreements in the PR**
  - Team members first discuss different opinions in the pull request.

- **Code steward makes the final call**
  - If the disagreement cannot be resolved, the responsible code steward makes the final decision.

- **Record important decisions**
  - Decisions that affect the overall project design should be documented in `DECISIONS.md`.


# Part 3 — Draft Evaluation Plan



Problem Grounding (10 minutes)
Three questions:

- Who specifically has the collaboration problem you are addressing? Name a real type of person, not a generic "user."
    - Small software development teams where multiple developers work on the same repository at the same time.
    - Student teams, small project teams, or teams using parallel branches / AI coding agents.

- What do they currently do instead of your tool?
    - Rely on team communication, issue trackers, pull requests, or experienced developers to coordinate work.
    - Potential conflicts are often discovered only after coding has started or during merging.
    - We may conduct a small survey or interview to better understand current workflows.
- What would be observably different about their collaboration if your tool worked?
    - Potential conflicts could be identified earlier and the number could be decreased
    - Software development pipeline will become faster
    - We can also compare whether a visualized coordination interface is more useful than simply asking an LLM for suggestions.

Evaluation Plan Draft (15 minutes)

- Success definition
    - We will know our tool works if it can identify potential collaboration conflicts early and provide warnings that developers consider useful.
    - AI suggests possible conflicts and affected modules; developers decide whether the warning is relevant and how to respond.
    - To be able to detect potential conflicts from our visualization tool easier
    - To be able to scan existing github repositories and find potential conflicts

- Target users
    - Small software development teams working on the same repository.
    - Developers who frequently use parallel branches, worktrees, or AI coding tools.


- Method
    - Scan existing github repositories, predict potential conflicts, and evaluate the prediction success rate
    - Conduct an user study based on the visualization tools that we provided
- Minimum evidence threshold
    - We currently expect a prediction success higher than 60%.


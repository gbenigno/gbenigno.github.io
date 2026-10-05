# Repository Guidelines

This is Gabriel Benigno's static GitHub Pages website. `index.html` contains
the homepage, inline CSS, and structured data. `website/index.html` redirects
the old URL to the homepage, preserving query parameters and fragments.
There is no package installation or build step. Preserve the responsive layout,
light/dark themes, and legacy redirect when editing the site.

## Validation

Run `bash scripts/checkpoint.sh check` from the repository root. It checks Git
whitespace, basic HTML document structure, JSON-LD, local href/src targets, and
the checkpoint regression tests. These are smoke checks, not a full HTML, CSS,
or JavaScript validator; external URLs are not fetched.

For visual or behavior changes, serve the repository with
`python3 -m http.server 8000` and inspect affected pages in a browser, including
mobile layout, both color schemes, and the redirect when affected. For tooling
or documentation changes with no visual effect, review the diff instead.

## Automatic Checkpoints

The user authorizes Codex to review all uncommitted repository changes and commit
and push completed, coherent updates to `origin` on the current branch without
asking for confirmation each time. This includes edits made by the user or before
the current task, whether staged or unstaged, and new files intended for the project.
Use the existing Codex session to assess readiness and write the commit message;
do not use a separate AI API. This is a task-completion workflow, not a file watcher.

- At the start of work and before finishing, inspect the whole working tree,
  including staged, unstaged, and untracked files. Preserve existing edits while
  reviewing them; their origin or age is not a reason to leave them uncommitted.
- Accumulate unfinished work and minor adjustments until a coherent content,
  style, or tooling update is complete. Do not commit after every tool call.
- Run `bash scripts/checkpoint.sh check` and perform the review described above.
- After successful review, run `bash scripts/checkpoint.sh ship --reviewed
  -m "Descriptive imperative subject" -- <exact changed file paths>`.
  The `--reviewed` flag records your completed review, not an extra user approval.
  Include ready pre-existing edits under this standing authorization, grouping
  independent changes into coherent checkpoints where practical. Exclude ignored
  files, scratch files, incomplete work, and anything explicitly kept local.
- If checks or review fail, or the update is incomplete, leave it local and explain
  what remains. Never skip review or invent a generic commit message as a fallback.
  Changes after `check` require another check and review.
- Never force-push or automatically resolve divergent remote history. If a push
  fails after the commit, use `bash scripts/checkpoint.sh retry-push` once the
  connection is restored; otherwise report the blocker and preserve local work.
- User instructions to hold off committing or pushing override this default.
- Before finishing, check Git status again. Account for remaining uncommitted
  changes and explain why they are held; do not silently leave ready edits behind.

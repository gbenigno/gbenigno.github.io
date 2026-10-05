# Gabriel Benigno's website

Static GitHub Pages site: `index.html` is the homepage and `website/index.html`
redirects the legacy URL. Serve locally with `python3 -m http.server 8000`.

## Automatic Git checkpoints

Adapted from `~/postdoc-beamer`. Under `AGENTS.md`, Codex reviews all uncommitted
work and commits and pushes completed, coherent updates to `origin` on the
current branch. This includes ready user edits, pre-existing changes, and new
project files. The active session judges readiness and writes the commit message.
There is no background watcher, Git hook, or additional AI API. Work done outside
a session enters review in the next session. Incomplete work and files explicitly
kept local are held, with the reason reported.

```sh
bash scripts/checkpoint.sh check
# Review the diff and, for visual or behavior changes, affected pages.
bash scripts/checkpoint.sh ship --reviewed -m "Update research description" -- index.html
```

`check` runs whitespace checks, basic HTML/JSON-LD/local-link checks, and workflow
regression tests, then records the working-tree state in ignored `.cache/`.
It does not validate all HTML/CSS/JavaScript, fetch external URLs, or inspect
rendered pages. `ship` requires unchanged checked files, explicit review, exact
file paths, and matching local/remote branch tips. Staged files outside the
selection stop shipping. It never force-pushes or reconciles divergence.

After a failed push, `bash scripts/checkpoint.sh retry-push` retries the recorded
commit only, provided HEAD and the current branch still match it.

Requires Git with an authenticated `origin`, a configured commit identity, and
Python 3.9+. The helper prefers `.tools/python3` if present, otherwise `python3`
on PATH. This checkout's ignored `.tools/python3` links to the working Python
installation in `~/postdoc-beamer`; fresh checkouts should use their own Python.

Tell Codex to hold off committing or pushing to pause this workflow. Remove the
Automatic Checkpoints section of `AGENTS.md` to disable it permanently.

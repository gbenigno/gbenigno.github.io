"""Check, review, then publish an explicitly selected website checkpoint."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".cache/checkpoint"
REVIEW = STATE / "review.json"
PENDING = STATE / "pending-push.json"


def run(*args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def git(*args):
    return run("git", *args, stdout=subprocess.PIPE).stdout.decode().strip()


def fail(message):
    raise RuntimeError(message)


def changed_paths():
    paths = set()
    for args in (("diff", "HEAD", "--name-only", "-z"),
                 ("ls-files", "--others", "--exclude-standard", "-z")):
        paths.update(p for p in run("git", *args, stdout=subprocess.PIPE)
                     .stdout.decode().split("\0") if p)
    return sorted(paths)


def snapshot():
    digest = hashlib.sha256()
    digest.update(git("rev-parse", "HEAD").encode())
    for name in changed_paths():
        path = ROOT / name
        digest.update(name.encode() + b"\0")
        if path.is_symlink():
            digest.update(b"link:" + os.readlink(path).encode())
        elif path.is_file():
            digest.update(str(path.stat().st_mode).encode())
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        elif path.exists():
            fail(f"Unsupported changed path: {name}")
        else:
            digest.update(b"deleted")
    return digest.hexdigest()


def write_state(path, value):
    STATE.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def branch():
    name = git("symbolic-ref", "--quiet", "--short", "HEAD")
    if not name:
        fail("Detached HEAD; select a branch first.")
    for marker in ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD", "rebase-merge", "rebase-apply"):
        if (ROOT / git("rev-parse", "--git-path", marker)).exists():
            fail("Finish the active Git operation before checkpointing.")
    return name


def check():
    REVIEW.unlink(missing_ok=True)
    branch()
    before = snapshot()
    run("git", "diff", "HEAD", "--check")
    run(sys.executable, "-B", str(ROOT / "scripts/check_site.py"))
    run(sys.executable, "-B", "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py")
    if before != snapshot():
        fail("Files changed during checks. Run check again.")
    write_state(REVIEW, {"snapshot": snapshot()})
    print("Website and workflow checks passed. Review changes, then run ship --reviewed.")


def ship(args):
    if not args.reviewed:
        fail("Review the changes and affected pages, then pass --reviewed.")
    message = args.message.strip()
    if not message or "\n" in message or len(message) > 72:
        fail("Supply a descriptive, single-line commit message of at most 72 characters.")
    if not REVIEW.exists() or json.loads(REVIEW.read_text()).get("snapshot") != snapshot():
        fail("No current successful check record. Run check and review the result again.")
    current_branch = branch()
    if PENDING.exists():
        fail("A checkpoint is waiting to be pushed; run retry-push first.")
    selected = set(args.paths)
    staged = set(run("git", "diff", "--cached", "--name-only", "-z",
                     stdout=subprocess.PIPE).stdout.decode().split("\0")) - {""}
    if staged - selected:
        fail("Staged changes outside the reviewed selection: " + ", ".join(sorted(staged - selected)))
    changed = set(changed_paths())
    tracked = set(run("git", "ls-files", "-z", stdout=subprocess.PIPE).stdout.decode().split("\0"))
    if not selected & changed or not selected <= (tracked | changed):
        fail("List exact repository file paths after --, with at least one changed file; no directories.")
    # Refresh the remote before committing. Never publish older local commits as a side effect.
    run("git", "fetch", "origin", current_branch)
    if git("rev-parse", "HEAD") != git("rev-parse", "FETCH_HEAD"):
        fail("Local and remote branches differ. Reconcile them explicitly, then recheck and review.")
    if json.loads(REVIEW.read_text()).get("snapshot") != snapshot():
        fail("Files changed during validation. Run check and review again.")
    run("git", "add", "--", *sorted(selected))
    if set(git("diff", "--cached", "--name-only").splitlines()) != selected & changed:
        fail("The staged files differ from the selection. Inspect the index before continuing.")
    run("git", "diff", "--cached", "--check")
    run("git", "commit", "-m", message)
    write_state(PENDING, {"commit": git("rev-parse", "HEAD"), "branch": current_branch})
    REVIEW.unlink(missing_ok=True)
    retry_push()


def retry_push():
    if not PENDING.exists():
        fail("No checkpoint is waiting for a push.")
    pending = json.loads(PENDING.read_text())
    if branch() != pending["branch"] or git("rev-parse", "HEAD") != pending["commit"]:
        fail("HEAD changed since the checkpoint. Inspect it before pushing manually.")
    run("git", "push", "origin", f"{pending['commit']}:refs/heads/{pending['branch']}")
    PENDING.unlink()
    print("Checkpoint committed and pushed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Check the website and workflow, then record the working-tree state")
    shipping = commands.add_parser("ship", help="Commit and push only the reviewed file selection")
    shipping.add_argument("--reviewed", action="store_true")
    shipping.add_argument("-m", "--message", required=True)
    shipping.add_argument("paths", nargs="+")
    commands.add_parser("retry-push", help="Retry exactly the last checkpoint after a push failure")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    # Concurrent checkpoint commands must not race on the index or review records.
    import fcntl
    with (STATE / "lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail("Another checkpoint command is running.")
        if args.command == "check":
            check()
        elif args.command == "ship":
            ship(args)
        else:
            retry_push()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError) as error:
        print(f"Checkpoint held: {error}", file=sys.stderr)
        sys.exit(1)

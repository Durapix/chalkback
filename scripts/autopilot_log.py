"""Export the repository's history as JSON for the landing page's "built on autopilot" section.

Every merge into main (local merges and GitHub pull requests) is a merged pull request;
tags are releases.
Usage: python scripts/autopilot_log.py > landing/autopilot.json
"""

import json
import re
import subprocess
import sys
from pathlib import Path

SEP = "\x1f"
REC = "\x1e"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def _plain(markdown: str) -> str:
    """One changelog bullet as plain text, at most about two sentences."""
    text = re.sub(r"\*\*([^*]+)\*\*|`([^`]+)`", lambda m: m.group(1) or m.group(2), markdown)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", " ".join(text.split()))
    sentences = re.split(r"(?<=[.!?])\s+", text)
    short = " ".join(sentences[:2])
    return short if len(short) <= 220 else short[:217].rsplit(" ", 1)[0] + "…"


def release_notes() -> dict[str, dict]:
    """Per version: the intro paragraph and the bullets of each group (Added, Fixed, ...)."""
    notes: dict[str, dict] = {}
    version = group = None
    bullet: list[str] = []

    def flush() -> None:
        if version and group and bullet:
            notes[version]["groups"].setdefault(group, []).append(_plain(" ".join(bullet)))
        bullet.clear()

    for line in CHANGELOG.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ["):
            flush()
            version, group = line[4:].split("]", 1)[0], None
            notes[version] = {"intro": "", "groups": {}}
        elif version is None or line.startswith("["):
            continue
        elif line.startswith("### "):
            flush()
            group = line[4:].strip()
        elif line.startswith("- "):
            flush()
            bullet.append(line[2:])
        elif line.startswith("  ") and bullet:
            bullet.append(line.strip())
        elif line.strip() and group is None:
            notes[version]["intro"] = (notes[version]["intro"] + " " + line.strip()).strip()
        elif not line.strip():
            flush()
    flush()
    return notes


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ref = sys.argv[1] if len(sys.argv) > 1 else "main"
    raw = git("log", ref, "--first-parent", f"--format=%H{SEP}%cI{SEP}%s{SEP}%b{REC}")
    merges, commits_total = [], int(git("rev-list", "--count", ref).strip())
    for entry in filter(None, (e.strip() for e in raw.split(REC))):
        sha, date, subject, body = (entry.split(SEP) + [""] * 4)[:4]
        if subject.startswith("Merge pull request"):
            # GitHub: "Merge pull request #5 from owner/branch"; the body is the PR title.
            branch = subject.split(" from ", 1)[1].split("/", 1)[-1]
        elif subject.startswith("Merge branch"):
            branch = subject.split("'")[1] if "'" in subject else subject
        else:
            continue
        body_lines = [ln for ln in body.strip().splitlines() if not ln.startswith("Co-Authored-By")]
        commits = int(git("rev-list", "--count", f"{sha}^1..{sha}^2").strip())
        merges.append(
            {
                "sha": sha[:7],
                "date": date,
                "branch": branch,
                "summary": " ".join(body_lines).strip(),
                "commits": commits,
                "review_fixes": int(
                    git("log", "--format=%s", f"{sha}^1..{sha}^2").count("fix(")
                ),
            }
        )
    notes = release_notes()
    tags = []
    for line in git("tag", "--sort=-creatordate", "--format=%(refname:short)|%(creatordate:iso-strict)").splitlines():
        name, _, date = line.partition("|")
        tags.append({"name": name, "date": date, **notes.get(name.removeprefix("v"), {})})
    json.dump(
        {"commits": commits_total, "merges": merges, "releases": tags},
        sys.stdout,
        indent=2,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

"""Export the repository's history as JSON for the landing page's "built on autopilot" section.

Every merge into main is treated as a merged pull request; tags are releases.
Usage: python scripts/autopilot_log.py > landing/autopilot.json
"""

import json
import subprocess
import sys

SEP = "\x1f"
REC = "\x1e"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


def main() -> None:
    raw = git("log", "main", "--first-parent", f"--format=%H{SEP}%cI{SEP}%s{SEP}%b{REC}")
    merges, commits_total = [], int(git("rev-list", "--count", "main").strip())
    for entry in filter(None, (e.strip() for e in raw.split(REC))):
        sha, date, subject, body = (entry.split(SEP) + [""] * 4)[:4]
        if not subject.startswith("Merge branch"):
            continue
        branch = subject.split("'")[1] if "'" in subject else subject
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
    tags = []
    for line in git("tag", "--sort=-creatordate", "--format=%(refname:short)|%(creatordate:iso-strict)").splitlines():
        name, _, date = line.partition("|")
        tags.append({"name": name, "date": date})
    json.dump(
        {"commits": commits_total, "merges": merges, "releases": tags},
        sys.stdout,
        indent=2,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

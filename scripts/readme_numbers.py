#!/usr/bin/env python3
"""readme_numbers.py — keep the README's entry count equal to the shelf.

WHY THIS EXISTS
---------------
On 2026-08-30 the README's headline read "459 curated entries" while the shelves held
506. Off by forty-seven. Nobody lied; the number was typed by hand once and every merge
after that made it a little more wrong. It is the first sentence a stranger reads and it
is the product claim.

The fix is not "remember to update it." A rule enforced by remembering is not a rule --
that same day the boot card's own hard line cap was overshot twice in two days for
exactly this reason. So the number is computed from the files and written by a machine.

WHAT THIS OWNS, AND WHAT IT DOES NOT
------------------------------------
It owns ONLY what sits between the fence markers:

    <!--COUNT:START-->506<!--COUNT:END-->
    <!--SHELVES:START-->13<!--SHELVES:END-->

Everything else in the README is human prose and this script must never touch it. The
marker pattern is borrowed from NEW-THIS-WEEK, which has worked here since it shipped.

**It deliberately does NOT police the CLAIMS.** The same audit that found 459-vs-506 also
found "No dead links." standing as an absolute the shelf could not support, and "every one
checked by hand" surviving past the day the Submission Gate started verifying submissions
by itself. No cron would ever have caught either. Those need a human read after every
merge -- that is a separate standing rule and this script is not a substitute for it. If
you are reading this because you assumed the bot had the README covered: it has the
NUMBERS covered. That is all.

FAIL CLOSED
-----------
This has write access to the public front door. A wrong number written confidently by a
machine is worse than a stale one, because nobody re-checks a bot -- that is precisely how
the 24K Vault's monthly audit filed a passing report every month for four months while
checking nothing. So: if any shelf is missing, unreadable, or cannot be counted, this refuses
to write anything and opens a ticket. A partial count is never published.

EMPTY SHELVES
-------------
A shelf may be empty on purpose. It says so with a line that starts `_No entries yet._`,
and then zero is its honest count. The two states are kept apart strictly:

    no entries, has the line   -> counted as 0
    no entries, no line        -> refused: the entries could not be read
    has entries, has the line  -> refused: the line is now false, remove it

The folder and the SHELVES list below must also agree. A shelf file that is not on the
list is refused rather than silently left out of the count (2026-10-10: four shelves were
added and this kept counting thirteen).

TICKETS
-------
One open ticket at a time, and it speaks only when there is something new to say. If the
ticket already reports exactly this problem, a later failing run adds nothing; the run
still fails, which is the signal. When the problem changes it adds one comment. When the
count is written again it says so and closes the ticket itself.

RUNNING IT BY HAND
------------------
Outside GitHub Actions this only looks: it prints the count and any problems, writes
nothing and posts nothing. `--dry-run` forces the same inside Actions. (2026-10-12: run
from a terminal for its help text, the old version filed a public comment.)
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "Haustorium12/gold-402")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
DIRECTORY = os.path.join(ROOT, "directory")

# The canonical shelf list. Named explicitly rather than globbed: a glob silently
# counts a new file as a shelf and silently stops noticing a deleted one. If a shelf
# is genuinely added, this list is the deliberate act that admits it.
SHELVES = [
    "apis", "mcp-servers", "sdks", "facilitators", "frameworks", "tools",
    "security", "ecosystem", "aggregators", "global", "learning",
    "community", "market-data", "examples", "use-cases", "research",
    "publishers",
]

# An entry is a top-level markdown bullet opening with a link. Same shape the
# CONTRIBUTING format mandates: `- [Name](url) — Description.`
ENTRY = re.compile(r"^- \[", re.MULTILINE)

# How a shelf says it is empty on purpose. See EMPTY SHELVES above.
EMPTY_SIGN = re.compile(r"^_No entries yet\._", re.MULTILINE)

TICKET_TAG = "[readme-numbers]"  # how this bot recognises its own open ticket

# Tickets and README writes happen only when GitHub Actions runs this. Anywhere else,
# and with --dry-run, it looks and reports. See RUNNING IT BY HAND above.
IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"
DRY_RUN = (not IN_ACTIONS) or ("--dry-run" in sys.argv[1:])

USAGE = """usage: readme_numbers.py [--dry-run] [--help]

Counts the entries on the shelves in directory/ and keeps the two numbers in README.md
equal to them.

  --dry-run   count and report only: write nothing, post nothing
  --help      show this and exit

Outside GitHub Actions it always behaves as --dry-run.
"""


def api(method: str, path: str, payload: dict | None = None):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        method=method,
        data=json.dumps(payload).encode() if payload else None,
        headers={
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "gold-402-readme-numbers",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read() or "{}")


def open_ticket() -> dict | None:
    """This bot's own open ticket, if there is one."""
    existing = api("GET", f"/repos/{REPO}/issues?state=open&per_page=100")
    for issue in existing:
        if "pull_request" in issue:
            continue
        if TICKET_TAG in issue.get("title", ""):
            return issue
    return None


def latest_report(issue: dict) -> str:
    """The last thing said on the ticket: its newest comment, or its body if none."""
    comments = api(
        "GET", f"/repos/{REPO}/issues/{issue['number']}/comments?per_page=100"
    )
    if comments:
        return comments[-1].get("body") or ""
    return issue.get("body") or ""


def report_failure(title_suffix: str, body: str, detail: str) -> None:
    """Open a ticket, or add to the one already open -- and only if this is news.

    `detail` is the part of the report that names the problem. If the ticket's latest
    report already contains it, nothing is posted: the failing run is the signal, and a
    ticket that repeats itself on every run teaches everyone to stop reading it.
    """
    if DRY_RUN:
        print("dry run — no ticket filed", file=sys.stderr)
        return
    if not TOKEN:
        print("no token — cannot file a ticket; failing loudly instead", file=sys.stderr)
        return
    try:
        issue = open_ticket()
        if issue is not None:
            if detail in latest_report(issue):
                print(f"ticket #{issue['number']} already says this — not repeating it")
                return
            api(
                "POST",
                f"/repos/{REPO}/issues/{issue['number']}/comments",
                {"body": f"The problem has changed.\n\n{body}"},
            )
            print(f"commented on existing ticket #{issue['number']}")
            return
        created = api(
            "POST",
            f"/repos/{REPO}/issues",
            {
                "title": f"{TICKET_TAG} {title_suffix}",
                "labels": ["web", "bug"],
                "body": body,
            },
        )
        print(f"opened ticket #{created['number']}")
    except urllib.error.HTTPError as exc:
        # Ticketing failing must not be silent either.
        print(f"could not file ticket: HTTP {exc.code} {exc.reason}", file=sys.stderr)


def close_ticket(total: int, shelves: int) -> None:
    """The count is being written again: say so on the open ticket and close it."""
    if DRY_RUN or not TOKEN:
        return
    try:
        issue = open_ticket()
        if issue is None:
            return
        api(
            "POST",
            f"/repos/{REPO}/issues/{issue['number']}/comments",
            {
                "body": (
                    f"Counting again: **{total}** entries across **{shelves}** "
                    "shelves. Closing."
                )
            },
        )
        api(
            "PATCH",
            f"/repos/{REPO}/issues/{issue['number']}",
            {"state": "closed", "state_reason": "completed"},
        )
        print(f"closed ticket #{issue['number']}")
    except urllib.error.HTTPError as exc:
        # A ticket left open is a nuisance, not a wrong number. Say so and carry on.
        print(f"could not close ticket: HTTP {exc.code} {exc.reason}", file=sys.stderr)


def count_shelves() -> tuple[dict[str, int], list[str]]:
    counts: dict[str, int] = {}
    problems: list[str] = []
    for shelf in SHELVES:
        path = os.path.join(DIRECTORY, f"{shelf}.md")
        if not os.path.exists(path):
            problems.append(f"`directory/{shelf}.md` — MISSING")
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except OSError as exc:
            problems.append(f"`directory/{shelf}.md` — unreadable ({exc})")
            continue
        n = len(ENTRY.findall(text))
        signed = bool(EMPTY_SIGN.search(text))
        if n == 0 and not signed:
            problems.append(
                f"`directory/{shelf}.md` — no entries found and no `_No entries yet._` "
                "line. Either its entries could not be read, or the shelf is empty and "
                "needs that line"
            )
        elif n > 0 and signed:
            problems.append(
                f"`directory/{shelf}.md` — has {n} "
                f"{'entry' if n == 1 else 'entries'} but still says "
                "`_No entries yet._`. Remove that line"
            )
        counts[shelf] = n

    # The folder and the list must agree. A file that is not on the list would be
    # left out of the count without a word.
    on_disk = sorted(
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(DIRECTORY, "*.md"))
    )
    for name in on_disk:
        if name not in SHELVES:
            problems.append(
                f"`directory/{name}.md` — in the folder but not on this script's "
                "shelf list. Add it to `SHELVES` in `scripts/readme_numbers.py`, or "
                "move the file out of `directory/`"
            )
    return counts, problems


def replace_fenced(text: str, marker: str, value: str) -> tuple[str, int]:
    pattern = re.compile(
        rf"(<!--{marker}:START-->)(.*?)(<!--{marker}:END-->)", re.DOTALL
    )
    if not pattern.search(text):
        return text, -1  # marker absent — caller treats as fatal
    new_text, n = pattern.subn(rf"\g<1>{value}\g<3>", text)
    return new_text, n


def main() -> int:
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        print(USAGE)
        return 0
    unknown = [a for a in sys.argv[1:] if a != "--dry-run"]
    if unknown:
        print(f"unknown argument: {' '.join(unknown)}\n\n{USAGE}", file=sys.stderr)
        return 2
    if DRY_RUN:
        print("DRY RUN — nothing will be written and nothing will be posted")

    counts, problems = count_shelves()

    if problems:
        detail = "\n".join(f"- {p}" for p in problems)
        body = (
            "**The README count was not written.**\n\n"
            "The count is published only when every shelf can be counted, so a partial "
            "number never reaches the README.\n\n"
            f"### What went wrong\n\n{detail}\n\n"
            "### What the README still says\n\n"
            "Whatever it said before this run. It was not touched.\n\n"
            "### Done looks like\n\n"
            "The items above are resolved, this workflow runs green, and the count in "
            "the README matches the shelves. This issue then closes itself.\n\n"
            "_Filed automatically by `scripts/readme_numbers.py`._"
        )
        report_failure(
            "README count not written — a shelf could not be counted", body, detail
        )
        print("FAILED CLOSED — README untouched", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    total = sum(counts.values())
    shelves = len(counts)

    text = open(README, encoding="utf-8").read()
    original = text

    text, hits_count = replace_fenced(text, "COUNT", str(total))
    text, hits_shelves = replace_fenced(text, "SHELVES", str(shelves))

    if hits_count == -1 or hits_shelves == -1:
        body = (
            "**The fence markers are gone from README.md, so the count could not be "
            "written and nothing was changed.**\n\n"
            "This bot only ever edits what sits between:\n\n"
            "```\n<!--COUNT:START-->…<!--COUNT:END-->\n"
            "<!--SHELVES:START-->…<!--SHELVES:END-->\n```\n\n"
            "If those are missing, someone rewrote that part of the README by hand "
            "and dropped them. **That is not a crisis — but until the markers are back, "
            "the entry count is hand-maintained again**, which is the exact condition "
            "that produced 459-vs-506 on 2026-08-30.\n\n"
            f"Live count from the shelves right now: **{total}** across **{shelves}** shelves.\n\n"
            "### Done looks like\n\nMarkers restored around both numbers; this runs green.\n"
        )
        report_failure(
            "fence markers missing from README — count not written",
            body,
            "The fence markers are gone from README.md",
        )
        print("FAILED CLOSED — markers absent", file=sys.stderr)
        return 1

    breakdown = "  ".join(f"{k}={v}" for k, v in counts.items())
    if text == original:
        print(f"no change — README already says {total} across {shelves} shelves")
        print(f"  {breakdown}")
        close_ticket(total, shelves)
        return 0

    if DRY_RUN:
        print(f"README would be updated -> {total} across {shelves} shelves")
        print(f"  {breakdown}")
        return 0

    open(README, "w", encoding="utf-8").write(text)
    print(f"README count updated -> {total} across {shelves} shelves")
    print(f"  {breakdown}")
    close_ticket(total, shelves)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
test_entry_site.py -- the gate only passes a knock on the site being listed.

Added 2026-10-15. The hole: the gate knocked whatever url the PR description named,
while the shelf lists the url in the entry line. A description naming someone else's
live 402 passed a PR whose own line was dead. Found by this seat, and independently
by a GitHub Copilot review, whose scenario is case "copilot" below.

    python3 scripts/test_entry_site.py
"""

import http.server
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import submit_check  # noqa: E402
from extract_url import site, same_site  # noqa: E402

submit_check._blocked_ip = lambda ip: ip != "127.0.0.1"
submit_check.is_private_ip = lambda h: (False, None)
PORT = 8943
A = f"http://127.0.0.1:{PORT}"      # site "127.0.0.1"
B = f"http://localhost:{PORT}"      # site "localhost" -- a different operator


class _H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b""):
        self.send_response(code)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/.well-known/x402":
            return self._send(200, json.dumps({"resources": [f"{B}/live"]}).encode())
        self._send(402 if self.path == "/live" else 404)

    do_POST = do_GET


def gate(url, entry):
    """Run submit_check.main() in-process; return (result, reason)."""
    d = tempfile.mkdtemp()
    old = os.getcwd()
    os.chdir(d)
    sys.argv = ["submit_check.py", url, "", "service"]
    os.environ["ENTRY_URL"] = entry
    try:
        submit_check.main()
    except SystemExit:
        pass
    finally:
        os.chdir(old)
        os.environ.pop("ENTRY_URL", None)
    r = json.load(open(os.path.join(d, "submit_result.json")))
    return r["result"], r["reason"]


SITE_CASES = [
    ("api. and docs. on one domain are one site", "https://api.foo.com/x", "https://docs.foo.com/y", True),
    ("bare host and api. host are one site (Checkpoint402)", "https://checkpoint402.com", "https://api.checkpoint402.com/v1/a", True),
    ("mcp. and agents. are one site (Agent Hub, #336/#337)", "https://mcp.torbrooknews.com/mcp", "https://agents.torbrooknews.com/x", True),
    ("two customers on workers.dev are NOT one site", "https://a.workers.dev/x", "https://b.workers.dev/x", False),
    ("two customers on onrender.com are NOT one site", "https://evil.onrender.com/x", "https://dead.onrender.com/x", False),
    ("same workers.dev host is one site (Softbot)", "https://softbot-reader-mainnet.softbot.workers.dev/.well-known/x402", "https://softbot-reader-mainnet.softbot.workers.dev/v1/read", True),
    ("co.uk is a second-level suffix", "https://api.shop.co.uk/x", "https://other.co.uk/x", False),
    ("different domains are different sites", "https://live.example/x", "https://dead.example/x", False),
]

GATE_CASES = [
    ("copilot: live 402 in the description, a different site on the line -> FAIL",
     f"{A}/live", f"{B}/dead", "fail"),
    ("same site, live door -> PASS", f"{A}/live", f"{A}/listed", "pass"),
    ("no entry line (edit PRs, body-only submissions) -> unchanged, PASS", f"{A}/live", "", "pass"),
    ("manifest on the entry's site naming a door on another site -> FAIL",
     f"{A}/.well-known/x402", f"{A}/listed", "fail"),
]


def main():
    srv = http.server.HTTPServer(("127.0.0.1", PORT), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    fails = 0
    try:
        for name, a, b, want in SITE_CASES:
            ok = same_site(a, b) == want
            fails += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  ({site(a)} vs {site(b)})"))
        for name, url, entry, want in GATE_CASES:
            got, why = gate(url, entry)
            ok = got == want
            fails += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"\n      got {got}: {why}"))
    finally:
        srv.shutdown()
    n = len(SITE_CASES) + len(GATE_CASES)
    print(f"\n{n - fails}/{n} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
test_extract_url.py -- the four real submissions that shaped extract_url.py.

Every fixture is a body a stranger actually sent us. Two of them are the ones the
gate got wrong. Run it before touching the picker:  python3 scripts/test_extract_url.py
"""

import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from extract_url import pick, pick_example  # noqa: E402

CASES = [
    (
        "#183 Payfirst -- labelled line wins, and a Contact URL: line must not",
        "URL: https://www.payfirst.app/guides/x402-paid-links\n"
        "Category: Free learning resource (HTTP 200 expected).\n"
        "Contact URL: https://x.com/payfirst\n",
        "https://www.payfirst.app/guides/x402-paid-links",
        1,
    ),
    (
        "#175 x402-list -- lowercase label, Contact: line ignored",
        "Add x402-list to directory/aggregators.md.\n\n"
        "endpoint: https://x402-list.com/api/v1/suggestions\n"
        'Example: {"text":"x402-list directory submission"}\n\n'
        "Contact: inbox@cosimomiccol.is\n",
        "https://x402-list.com/api/v1/suggestions",
        1,
    ),
    (
        "#180 Preflight -- query string with & and %, kept whole",
        "## Verification\n\n"
        "URL: https://x402.chikocorp.com/api/x402/preflight/audit?resource_url=https%3A%2F%2Fx402.chikocorp.com&method=GET\n",
        "https://x402.chikocorp.com/api/x402/preflight/audit?resource_url=https%3A%2F%2Fx402.chikocorp.com&method=GET",
        1,
    ),
    (
        "#185 FractalAI -- no label; manifest beats the inline npm link",
        "Seven pay-per-call proof endpoints on Base (x402 v2).\n\n"
        "Also shipping [`@fractalai/x402-pqc-witness`](https://www.npmjs.com/package/@fractalai/x402-pqc-witness), "
        "which adds attestation to any resource server.\n\n"
        "Live discovery manifest: https://fractalai.net.co/.well-known/x402.json\n",
        "https://fractalai.net.co/.well-known/x402.json",
        2,
    ),
    (
        "no manifest, no label -- skip the npm link, take the service",
        "Ships as [pkg](https://www.npmjs.com/package/thing) and runs at https://pay.example.com/api/quote\n",
        "https://pay.example.com/api/quote",
        3,
    ),
    (
        "library submission -- a repo link is all there is, and that is fine",
        "An x402 middleware for Axum. Source: https://github.com/someone/axum-x402\n",
        "https://github.com/someone/axum-x402",
        4,
    ),
    (
        "empty body -- no url, no crash",
        "",
        "",
        0,
    ),
    (
        "#268 x402risk -- body names paths only, no host; the entry line is the door",
        "## Add x402risk\n\nBase, USDC, x402 v2 exact, payTo `0x8F9C3f91628497E2A72D6740022D46f87A9eB417`.\n\n"
        "Endpoints:\n- POST /v1/token-check $0.01\n\n"
        'Example: {"token":"0x532f27101965dd16442E59d40670FaF5eBB142E4"}\n',
        "https://api.x402risk.com/v1/token-check",
        5,
        "- [x402risk](https://api.x402risk.com/v1/token-check) — Base token scam/safety check.",
    ),
    (
        "tier 5 never outranks the body -- a url in the description still wins",
        "Manifest: https://svc.example.com/.well-known/x402\n",
        "https://svc.example.com/.well-known/x402",
        1,
        "- [Svc](https://svc.example.com/other) — Thing.",
    ),
    (
        "nothing anywhere -- empty, not a guess",
        "Please add us.",
        "",
        0,
        "",
    ),
]


# THE 2026-10-14 DOOR -- five false reds in one day, two of them this file's.
CASES += [
    (
        "#340 Checkpoint402 -- body names the bare marketing host; the entry line's route wins",
        "Adds Checkpoint402 Sanctions Screening to the security shelf.\n"
        "Homepage: https://checkpoint402.com\n",
        "https://api.checkpoint402.com/v1/sanctions-screen",
        3,
        "- [Checkpoint402 Sanctions Screening](https://api.checkpoint402.com/v1/sanctions-screen) — "
        "Screens a name or wallet against OFAC, $0.05 USDC per call on Base.",
    ),
    (
        "bare host in the body, no entry line -- unchanged, tier 3 on the host",
        "See https://example-x402.dev for details\n",
        "https://example-x402.dev",
        3,
    ),
    (
        "body url has a route -- the entry line does not override it",
        "Try https://svc.example.dev/v1/quote first.\n",
        "https://svc.example.dev/v1/quote",
        3,
        "- [Svc](https://svc.example.dev/v1/other) — a line.",
    ),
]

EXAMPLE_CASES = [
    (
        "#175 shape -- Example: line in the body wins over the entry line",
        'endpoint: https://x402-list.com/api/v1/suggestions\nExample: {"text":"hi"}\n',
        '- [x](https://x402-list.com/api/v1/suggestions) — `POST /x {"other":1}`',
        '{"text":"hi"}',
    ),
    (
        "#345 Softbot -- no Example: line; the JSON on the entry line is the body",
        "Adds Softbot Email Check.\n",
        "- [Softbot Email Check](https://softbot-emailcheck-mainnet.softbot.workers.dev/.well-known/x402) — "
        'Checks deliverability, $0.002 USDC per call. `POST /v1/email {"email":"a@example.com"}`',
        '{"email":"a@example.com"}',
    ),
    (
        "braces that are not JSON on the entry line -- ignored, empty-body probe",
        "Adds a thing.\n",
        "- [Thing](https://thing.dev/.well-known/x402) — returns {verdict, score} per call.",
        "",
    ),
    (
        "nothing anywhere -- empty",
        "Adds a thing.\n",
        "- [Thing](https://thing.dev/v1/go) — a line.",
        "",
    ),
]


def main() -> int:
    failures = 0
    for name, body, added, want in EXAMPLE_CASES:
        got = pick_example(body, added)
        ok = got == want
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failures += 1
            print(f"      want {want!r}, got {got!r}")
    for case in CASES:
        name, body, want_url, want_tier = case[:4]
        added = case[4] if len(case) > 4 else ""
        url, tier, why = pick(body, added)
        ok = url == want_url and tier == want_tier
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failures += 1
            print(f"      want tier {want_tier} {want_url!r}")
            print(f"      got  tier {tier} {url!r}  ({why})")
    total = len(CASES) + len(EXAMPLE_CASES)
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

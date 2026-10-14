#!/usr/bin/env python3
"""
test_manifest_doors.py -- the manifest path of submit_check.py: the doors it finds
in a manifest, and the body it knocks with.

Added 2026-10-14 after the door of that day put five false reds on working
services. Three (Softbot #343/#344/#345) were POST-only routes that answer `{}`
with 400 and 402 only once the body carries the field their manifest says is
required. The gate knocked with `{}` whatever the PR said, and never read the
schema it had already fetched. This runs a loopback server in the shapes that
bit us and checks the gate's answer, never a stranger's. Run before touching
manifest_doors(), body_from_schema() or the manifest branch of main():

    python3 scripts/test_manifest_doors.py
"""

import http.server
import json
import sys
import threading

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import submit_check  # noqa: E402
from submit_check import manifest_doors, body_from_schema, probe_for_402  # noqa: E402

submit_check._blocked_ip = lambda ip: ip != "127.0.0.1"
PORT = 8932
BASE = f"http://127.0.0.1:{PORT}"

MANIFEST = {
    "x402Version": 2,
    "resources": [
        # Softbot shape: POST-only, validates the body before the 402, declares input.
        {"resource": f"{BASE}/v1/email", "method": "POST",
         "input": {"type": "object", "required": ["email"],
                   "properties": {"email": {"type": "string"}}}},
        # x402 v2 shape: `resource` is an object (Verdix's note on #326).
        {"resource": {"url": f"{BASE}/v1/plain"}, "method": "GET"},
        # Dead door with a schema: must stay dead after the schema retry.
        {"resource": f"{BASE}/v1/dead", "method": "POST",
         "input": {"required": ["q"], "properties": {"q": {"type": "string"}}}},
        # Bare string, relative path.
        "POST /v1/rel",
    ],
}


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        if self.path == "/.well-known/x402":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(MANIFEST).encode())
            return
        self.send_response(402 if self.path == "/v1/plain" else 405)
        self.end_headers()

    def do_POST(self):
        body = self._body()
        if self.path == "/v1/email":
            self.send_response(402 if "email" in body else 400)
        elif self.path == "/v1/dead":
            self.send_response(400)       # never 402, whatever you send
        else:
            self.send_response(404)
        self.end_headers()


def main() -> int:
    srv = http.server.HTTPServer(("127.0.0.1", PORT), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    failures = 0

    def check(name, ok, detail=""):
        nonlocal failures
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failures += 1
            print(f"      {detail}")

    try:
        doors, err = manifest_doors(f"{BASE}/.well-known/x402")
        urls = [u for u, _ in doors]
        check("manifest read, no error", err is None, str(err))
        check("four doors found, v2 object and relative path included",
              urls == [f"{BASE}/v1/email", f"{BASE}/v1/plain", f"{BASE}/v1/dead", f"{BASE}/v1/rel"],
              str(urls))
        schema = dict(doors)[f"{BASE}/v1/email"]
        check("input schema carried alongside its door", schema and schema.get("required") == ["email"], str(schema))
        check("no schema on the v2 object door", dict(doors)[f"{BASE}/v1/plain"] is None)

        built = body_from_schema(schema)
        check("schema -> one placeholder per required field, typed",
              json.loads(built) == {"email": "example"}, built.decode())
        check("no schema -> no body", body_from_schema(None) == b"")
        check("schema with no fields -> no body", body_from_schema({"type": "object"}) == b"")
        check("nullable type picks the non-null",
              json.loads(body_from_schema({"required": ["n"], "properties": {"n": {"type": ["null", "integer"]}}})) == {"n": 1})

        code, _ = probe_for_402(f"{BASE}/v1/email")
        check("Softbot shape: empty body is a 400, not a pass", code == 400, str(code))
        code, _ = probe_for_402(f"{BASE}/v1/email", built)
        check("Softbot shape: schema body reaches the 402", code == 402, str(code))
        code, _ = probe_for_402(f"{BASE}/v1/dead", body_from_schema(dict(doors)[f"{BASE}/v1/dead"]))
        check("dead door: schema body does not turn a 400 into a pass", code == 400, str(code))
        code, _ = probe_for_402(f"{BASE}/v1/plain")
        check("v2 object door: POST 405 -> GET 402 via the existing retry", code == 402, str(code))
    finally:
        srv.shutdown()

    total = 12
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

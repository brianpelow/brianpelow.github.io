"""Fill the generated regions of a surface from the portfolio's own generators.

Fetches the blocks published by code-compliance-auditor and writes them between
this file's markers. Runs in the consumer repo's own workflow with its own
GITHUB_TOKEN, so no cross-repo token is ever needed.

Guards, in order of how badly each failure would show:

- A failed fetch aborts. A partial write would blank the catalog on a live page,
  which is worse than serving yesterday's copy for one more day.
- Output is asserted pure-ASCII before writing. The CI guard fails the build on
  any non-ASCII in index.html; catching it here names the offending block.
- An unchanged file exits 0 without touching disk, so the nightly does not
  produce an empty commit every night.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

RAW = (
    "https://raw.githubusercontent.com/brianpelow/"
    "code-compliance-auditor/main/generated/"
)
REGIONS = {"STATS": "stats_block.html", "CATALOG": "catalog_block.html"}
TIMEOUT = 30


def fetch(name: str) -> str:
    url = RAW + name
    req = urllib.request.Request(url, headers={"User-Agent": "portfolio-splice"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        if resp.status != 200:
            raise SystemExit(f"FAIL: {url} returned HTTP {resp.status}")
        body = resp.read().decode("utf-8")
    if not body.strip():
        raise SystemExit(f"FAIL: {url} was empty")
    return body.rstrip("\n")


def splice(text: str, region: str, block: str) -> str:
    start, end = f"<!-- {region}:START -->", f"<!-- {region}:END -->"
    if start not in text or end not in text:
        raise SystemExit(f"FAIL: markers for {region} not found in index.html")
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    return f"{head}{start}\n{block}\n  {end}{tail}"


def main() -> int:
    path = Path("index.html")
    original = path.read_text(encoding="utf-8")
    text = original

    for region, filename in REGIONS.items():
        block = fetch(filename)
        print(f"[splice] fetched {filename} ({len(block)} chars)")
        text = splice(text, region, block)

    offenders = sorted({c for c in text if ord(c) > 127})
    if offenders:
        codes = ", ".join(f"U+{ord(c):04X}" for c in offenders)
        raise SystemExit(f"FAIL: spliced output contains non-ASCII: {codes}")

    if text == original:
        print("[splice] no change")
        return 0

    path.write_text(text, encoding="utf-8")
    print(f"[splice] wrote index.html ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

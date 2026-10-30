from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

DOI = "doi:10.5061/dryad.1c59zw48r"
API = f"https://datadryad.org/api/v2/datasets/{urllib.parse.quote(DOI, safe='')}/download"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the published TMC-Tongue dataset from Dryad")
    parser.add_argument("--output", type=Path, default=Path("data/tmc_tongue"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(API, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request) as response:
        package = json.load(response)
    files = package.get("data", [])
    if not files:
        raise RuntimeError("Dryad did not return downloadable files")
    for item in files:
        attrs, links = item.get("attributes", {}), item.get("links", {})
        name, url = attrs.get("name"), links.get("download")
        if not name or not url:
            continue
        target = args.output / name
        print(f"downloading {name} -> {target}")
        urllib.request.urlretrieve(url, target)


if __name__ == "__main__":
    main()


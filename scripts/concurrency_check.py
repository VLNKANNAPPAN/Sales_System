"""Dependency-free, Docker-backed concurrency check for the running API."""

import argparse
import concurrent.futures
import json
import sys
import urllib.error
import urllib.request
from uuid import uuid4


def post_reservation(url: str, run_id: str, index: int) -> int:
    request = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Idempotency-Key": f"concurrency-{run_id}-{index}",
            "X-Client-ID": f"concurrency-client-{run_id}-{index}",
        },
    )
    try:
        return urllib.request.urlopen(request, timeout=20).status
    except urllib.error.HTTPError as error:
        return error.code


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=1005)
    parser.add_argument("--workers", type=int, default=150)
    parser.add_argument("--max-success", type=int, default=1000)
    parser.add_argument("--url", default="http://localhost:8001/v1/items/flash-sale-item/reservations")
    args = parser.parse_args()

    run_id = uuid4().hex
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        statuses = list(pool.map(lambda index: post_reservation(args.url, run_id, index), range(args.requests)))
    counts = {str(code): statuses.count(code) for code in sorted(set(statuses))}
    print(json.dumps(counts, indent=2))

    accepted = counts.get("202", 0)
    if accepted > args.max_success:
        sys.exit(f"FAILED: {accepted} reservations exceeded the {args.max_success} stock limit")
    print(f"PASS: {accepted} accepted reservations did not exceed {args.max_success} units.")


if __name__ == "__main__":
    main()

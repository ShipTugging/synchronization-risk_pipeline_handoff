"""Small utility for loading the synchronized.jsonl handoff file."""

import json


def load_synchronized_jsonl(path: str) -> list[dict]:
    """Parse a JSON Lines file into a list of record dicts."""
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


if __name__ == "__main__":
    import sys

    p = sys.argv[1] if len(sys.argv) > 1 else "synchronized.jsonl"
    recs = load_synchronized_jsonl(p)
    print(f"loaded {len(recs)} records from {p}")
    print(f"first timestamp_ms: {recs[0]['timestamp_ms']}")
    print(f"last timestamp_ms: {recs[-1]['timestamp_ms']}")

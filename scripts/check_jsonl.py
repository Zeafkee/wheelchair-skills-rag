import json
from json import JSONDecodeError
from pathlib import Path

paths = ["data/skills.jsonl", "data/faq.jsonl", "data/rubrics.jsonl"]

def check(path):
    p = Path(path)
    if not p.exists():
        print(f"SKIP (missing): {path}")
        return
    with p.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                json.loads(s)
            except JSONDecodeError as e:
                print(f"INVALID: {path}:{i}: {e}")
                print(s[:500])
                return
    print(f"OK: {path}")

for path in paths:
    check(path)
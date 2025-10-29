import re
from pathlib import Path

paths = ["data/skills.jsonl"]

def fix_inches(text: str) -> str:
    # Replace a double-quote that immediately follows a digit with a double-prime (U+2033)
    return re.sub(r'(?<=\d)"', "″", text)

for p in map(Path, paths):
    if not p.exists():
        print(f"SKIP (missing): {p}")
        continue
    original = p.read_text(encoding="utf-8")
    fixed = fix_inches(original)
    if fixed != original:
        bak = p.with_suffix(p.suffix + ".bak")
        bak.write_text(original, encoding="utf-8")
        p.write_text(fixed, encoding="utf-8")
        print(f"Fixed inch marks in {p} (backup at {bak})")
    else:
        print(f"No inch marks found to fix in {p}")
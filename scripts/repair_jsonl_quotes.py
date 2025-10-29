import re
from pathlib import Path

p = Path("data/skills.jsonl")
original = p.read_text(encoding="utf-8")

# Revert cases where a closing quote at the END of a string was mistakenly turned into ″
# Matches: digit + U+2033 (double-prime) followed by optional spaces and then a JSON delimiter , ] }
repaired = re.sub(r'(?<=\d)″(?=\s*[,}\]])', '"', original)

if repaired != original:
    bak = p.with_suffix(p.suffix + ".pre_repair.bak")
    bak.write_text(original, encoding="utf-8")
    p.write_text(repaired, encoding="utf-8")
    print(f"Repaired string-boundary quotes in {p} (backup at {bak})")
else:
    print("No boundary quote repairs needed")
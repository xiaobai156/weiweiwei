import re
from pathlib import Path

p = Path(__file__).resolve().parent / "liuxuan_index.html"
t = p.read_text(encoding="utf-8-sig")
i = t.find("preview")
print(t[i - 50: i + 2000])

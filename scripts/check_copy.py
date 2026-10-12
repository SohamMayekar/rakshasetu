"""Copy rules (CLAUDE.md §7, PRD §8.3): words the product must never show on screen or in API replies.
Comments that name a forbidden phrase in order to forbid it are fine; shown text is not.
    python3 scripts/check_copy.py      (part of `make test`)
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEVER = re.compile(r"help (?:is )?on (?:the|its) way|\blease\b|team silent|\bagentic\b|AI agent|triage agents|AI prioriti[sz]|"
                   r"22 languages|novel lease|tamper-proof|national command|₹0 tonight|dispatch NDRF|"
                   r"background heartbeat", re.IGNORECASE)
WHERE = ["apps/web/app", "apps/web/lib", "apps/web/components", "services/api/app/modules/public",
         "services/api/i18n", "apps/web/i18n"]
COMMENT = re.compile(r"^\s*(//|#|\*|/\*|\{/\*|\"\"\"|-)")


def main() -> int:
    hits = []
    for folder in WHERE:
        for path in (ROOT / folder).rglob("*"):
            if path.suffix not in {".ts", ".tsx", ".py", ".json"} or not path.is_file():
                continue
            in_docstring = False
            for n, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                if line.count('"""') == 1:
                    in_docstring = not in_docstring
                    continue
                if in_docstring or COMMENT.match(line):
                    continue
                if NEVER.search(line):
                    hits.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
    if hits:
        print("Copy rules broken (never show these words):\n" + "\n".join(hits))
        return 1
    print("copy rules: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())

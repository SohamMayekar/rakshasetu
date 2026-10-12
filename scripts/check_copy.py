"""Copy rules (CLAUDE.md §7, PRD §8.3, docs/SIMPLIFY_PLAN.md): words the product must never show on screen.
    python3 scripts/check_copy.py      (part of `make test`)

1. NEVER: the never-say words (§7), anywhere in screen code or public API replies.
2. JARGON (m66): words a judge shouldn't have to decode (provenance, SEOC, hash chain, ×60, P1 alone, …), in the
   text a screen shows: JSX text and string literals with a space in them, in the web app and in the backend
   lines the desk displays. The plain words are in apps/web/lib/words.ts and the plan's glossary.
Comments that name a forbidden phrase in order to forbid it are fine; shown text is not. A line that only
matches an API code (never shown) can say so with a trailing `copy-ok` comment.
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

JARGON = re.compile(
    r"\bprovenance\b|\buncertainty\b|\bresponsibility\b|\bS?EOC\b|\bIDOR\b|\bingest(?:ion|ed)?\b|\bannotations?\b|"
    r"\bwebhooks?\b|\bhash[- ]chain(?:ed)?\b|\bsha256\b|×60|\bP[1-4]\b|\bescalations?\b|\bpipeline\b|\bfixtures?\b|"
    r"\bSTT\b|\bLLM\b|\bdispatcher\b|\blanes?\b|\bp(?:50|95|99)\b|\bidempoten(?:t|cy)\b", re.IGNORECASE)
# Where shown text lives: the web app, and the backend lines the desk and the phones display word for word.
JARGON_WHERE = ["apps/web/app", "apps/web/lib", "apps/web/components", "services/api/app/modules/public",
                "services/api/app/modules/cases/timeline.py", "services/api/app/modules/escalations/ticker.py",
                "services/api/app/pipeline/run.py"]
JARGON_SKIP = {"apps/web/lib/words.ts",      # the glossary itself: it maps the API's codes to plain words
               "apps/web/app/ui"}            # the design-system reference page for the team (not linked from any screen)
STRING = re.compile(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|`((?:[^`\\]|\\.)*)`')
JSX_TEXT = re.compile(r">([^<>{}]+)<|>([^<>{}]+)$")
CODE = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|WHERE|FROM|JOIN|VALUES|RETURNING)\b")
CLASSES = re.compile(r"^[a-z0-9\-:/\[\]._%!#()&>~*\s]+$")   # a className list ("bg-p1/10 text-p1")


def shown_pieces(line: str, jsx: bool) -> list[str]:
    """The parts of a source line that end up as words on a screen (best effort, deliberately simple)."""
    out = []
    for m in STRING.finditer(line):
        t = re.sub(r"\$?\{[^}]*\}", "", next(g for g in m.groups() if g is not None))   # ${…} and f-string {…}: code
        if " " in t.strip() and not CODE.search(t) and not t.lstrip().startswith(("/v1", "http")) and not CLASSES.match(t):
            out.append(t)
    if jsx:
        for m in JSX_TEXT.finditer(STRING.sub('""', line)):
            t = next(g for g in m.groups() if g is not None)
            if re.search("[A-Za-z]", t) and not re.search(r"=>|&&|\|\||\?\s", t):
                out.append(t)
    return out


def scan(folders, pattern, pieces=None, skip=()):
    hits = []
    for folder in folders:
        base = ROOT / folder
        for path in ([base] if base.is_file() else base.rglob("*")):
            rel = str(path.relative_to(ROOT))
            if path.suffix not in {".ts", ".tsx", ".py", ".json"} or not path.is_file() or any(rel.startswith(s) for s in skip):
                continue
            in_docstring = False
            for n, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                if line.count('"""') == 1:
                    in_docstring = not in_docstring
                    continue
                if in_docstring or COMMENT.match(line) or line.lstrip().startswith(("import ", "from ")) or "copy-ok" in line:
                    continue
                for text in (pieces(line, path.suffix == ".tsx") if pieces else [line]):
                    if m := pattern.search(text):
                        hits.append(f"{rel}:{n}: {m.group(0)!r} in {text.strip()[:100]!r}")
    return hits


def main() -> int:
    never = scan(WHERE, NEVER)
    jargon = scan(JARGON_WHERE, JARGON, shown_pieces, JARGON_SKIP)
    if never:
        print("Copy rules broken (never show these words):\n" + "\n".join(never))
    if jargon:
        print("Jargon on a screen (use the plain words in apps/web/lib/words.ts / docs/SIMPLIFY_PLAN.md):\n" + "\n".join(jargon))
    if never or jargon:
        return 1
    print("copy rules: ok (never-say words and screen jargon)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

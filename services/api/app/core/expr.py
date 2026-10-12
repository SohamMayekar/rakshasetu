"""A tiny, safe expression language for the team-owned priority rules (PRD §9):

    "trapped and (water_rising or water_entering or medical_urgent)"
    "(buried or structure_collapsed) and people_count >= 1"
    "true"

Only names from a fixed list, integers, true/false, and/or/not and comparisons are allowed. It is parsed with
Python's `ast` and walked by hand; nothing is ever passed to eval(). A typo fails when the config loads.
"""

import ast

FACTS = {"trapped", "water_rising", "water_entering", "medical_urgent", "buried", "structure_collapsed",
         "landslide", "cut_off", "vulnerable", "infant", "elderly", "child", "pregnant", "disabled", "medicine",
         "needs_supplies", "people_count"}
_CMP = {ast.GtE: lambda a, b: a >= b, ast.Gt: lambda a, b: a > b, ast.LtE: lambda a, b: a <= b,
        ast.Lt: lambda a, b: a < b, ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}


class RuleError(ValueError):
    pass


def parse(source: str) -> ast.Expression:
    try:
        tree = ast.parse(source.replace("true", "True").replace("false", "False"), mode="eval")
    except SyntaxError as e:
        raise RuleError(f"can't read rule {source!r}: {e.msg}") from None
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in FACTS and node.id not in ("True", "False"):
            raise RuleError(f"unknown fact {node.id!r} in rule {source!r}; known facts: {sorted(FACTS)}")
        if not isinstance(node, (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.Compare,
                                 ast.Name, ast.Load, ast.Constant, *_CMP)):
            raise RuleError(f"rule {source!r} uses {type(node).__name__}, which isn't allowed")
    return tree


def evaluate(tree: ast.Expression, facts: dict) -> bool:
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.BoolOp):
            vals = (ev(v) for v in n.values)
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        if isinstance(n, ast.UnaryOp):
            return not ev(n.operand)
        if isinstance(n, ast.Compare):
            left = ev(n.left)
            for op, right in zip(n.ops, n.comparators, strict=True):
                r = ev(right)
                if left is None or r is None or not _CMP[type(op)](left, r):
                    return False
                left = r
            return True
        if isinstance(n, ast.Name):
            return True if n.id == "True" else False if n.id == "False" else facts.get(n.id)
        if isinstance(n, ast.Constant):
            return n.value
        raise RuleError(f"unsupported {type(n).__name__}")
    return bool(ev(tree))

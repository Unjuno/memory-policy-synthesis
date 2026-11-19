"""Small, bounded policy AST shared by generator and differential tests.

This is an off-kernel, userspace research DSL, NOT a Linux reclaim interface.
"""
from __future__ import annotations
import json
from pathlib import Path

FEATURES = {"idle_sec", "anon_kib", "psi_pct"}
LIMITS = {"idle_sec": 86_400, "anon_kib": 268_435_456, "psi_pct": 100}
U64_MAX = (1 << 64) - 1
MAX_LITERAL = 1_000_000_000
MAX_DEPTH = 12


class InvalidPolicy(ValueError):
    pass


def validate(expr: dict, depth: int = 0) -> None:
    if not isinstance(expr, dict) or depth > MAX_DEPTH:
        raise InvalidPolicy("policy must be an AST object with depth <= 12")
    op = expr.get("op")
    if op == "lit":
        if (set(expr) != {"op", "value"} or type(expr["value"]) is not int
                or not 0 <= expr["value"] <= MAX_LITERAL):
            raise InvalidPolicy("lit requires bounded nonnegative integer value")
    elif op == "feature":
        if set(expr) != {"op", "name"} or type(expr["name"]) is not str or expr["name"] not in FEATURES:
            raise InvalidPolicy("unknown feature")
    elif op in ("add", "sub", "min", "max"):
        if set(expr) != {"op", "left", "right"}:
            raise InvalidPolicy("invalid binary expression")
        validate(expr["left"], depth + 1)
        validate(expr["right"], depth + 1)
    elif op == "percent":
        if (set(expr) != {"op", "value", "expr"} or type(expr["value"]) is not int
                or not 0 <= expr["value"] <= 100):
            raise InvalidPolicy("percent must be between 0 and 100")
        validate(expr["expr"], depth + 1)
    elif op == "if_ge":
        if (set(expr) != {"op", "feature", "threshold", "then", "else"}
                or type(expr["feature"]) is not str or expr["feature"] not in FEATURES or type(expr["threshold"]) is not int
                or not 0 <= expr["threshold"] <= MAX_LITERAL):
            raise InvalidPolicy("invalid if_ge node")
        validate(expr["then"], depth + 1)
        validate(expr["else"], depth + 1)
    else:
        raise InvalidPolicy(f"unsupported operator: {op!r}")


def load_policy(path: str | Path) -> dict:
    obj = json.loads(Path(path).read_text())
    if not isinstance(obj, dict) or obj.get("version") != 1 or "expr" not in obj:
        raise InvalidPolicy("expected policy version 1 and expr")
    validate(obj["expr"])
    return obj["expr"]


def features(idle_sec: int, anon_kib: int, psi_pct: int) -> dict[str, int]:
    inputs = {"idle_sec": idle_sec, "anon_kib": anon_kib, "psi_pct": psi_pct}
    if any(type(v) is not int or not 0 <= v <= U64_MAX for v in inputs.values()):
        raise ValueError("feature inputs must be unsigned 64-bit integers")
    return {k: min(v, LIMITS[k]) for k, v in inputs.items()}


def eval_expr(expr: dict, f: dict[str, int]) -> int:
    op = expr["op"]
    if op == "lit":
        return expr["value"]
    if op == "feature":
        return f[expr["name"]]
    if op == "add":
        return min(U64_MAX, eval_expr(expr["left"], f) + eval_expr(expr["right"], f))
    if op == "sub":
        return max(0, eval_expr(expr["left"], f) - eval_expr(expr["right"], f))
    if op == "min":
        return min(eval_expr(expr["left"], f), eval_expr(expr["right"], f))
    if op == "max":
        return max(eval_expr(expr["left"], f), eval_expr(expr["right"], f))
    if op == "percent":
        return eval_expr(expr["expr"], f) * expr["value"] // 100
    if op == "if_ge":
        return eval_expr(expr["then"] if f[expr["feature"]] >= expr["threshold"]
                         else expr["else"], f)
    raise AssertionError("validated AST required")


def decide(expr: dict, idle_sec: int, anon_kib: int, psi_pct: int, cap_kib: int) -> int:
    if type(cap_kib) is not int or not 0 <= cap_kib <= U64_MAX:
        raise ValueError("cap must be an unsigned 64-bit integer")
    f = features(idle_sec, anon_kib, psi_pct)
    return 0 if idle_sec == 0 else min(cap_kib, f["anon_kib"], eval_expr(expr, f))


def c_expr(e: dict) -> str:
    op = e["op"]
    if op == "lit":
        return f'UINT64_C({e["value"]})'
    if op == "feature":
        return e["name"]
    if op in ("add", "sub", "min", "max"):
        fn = {"add": "sat_add", "sub": "sat_sub", "min": "min_u64", "max": "max_u64"}[op]
        return f'{fn}({c_expr(e["left"])}, {c_expr(e["right"])})'
    if op == "percent":
        return f'percent_u64({c_expr(e["expr"])}, UINT64_C({e["value"]}))'
    if op == "if_ge":
        return (f'({e["feature"]} >= UINT64_C({e["threshold"]}) ? '
                f'{c_expr(e["then"])} : {c_expr(e["else"])})')
    raise AssertionError(op)


def lean_expr(e: dict) -> str:
    op = e["op"]
    if op == "lit":
        return f'(Expr.lit {e["value"]})'
    if op == "feature":
        feat = {"idle_sec": "idleSec", "anon_kib": "anonKiB", "psi_pct": "psiPct"}[e["name"]]
        return f'(Expr.field Feature.{feat})'
    if op in ("add", "sub", "min", "max"):
        ctor = {"add": "plus", "sub": "minus", "min": "minimum", "max": "maximum"}[op]
        return f'(Expr.{ctor} {lean_expr(e["left"])} {lean_expr(e["right"])})'
    if op == "percent":
        return f'(Expr.percent {e["value"]} {lean_expr(e["expr"])})'
    if op == "if_ge":
        feat = {"idle_sec": "idleSec", "anon_kib": "anonKiB", "psi_pct": "psiPct"}[e["feature"]]
        return (f'(Expr.ifGe Feature.{feat} {e["threshold"]} '
                f'{lean_expr(e["then"])} {lean_expr(e["else"])})')
    raise AssertionError(op)

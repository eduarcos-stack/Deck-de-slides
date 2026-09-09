"""Testes do M11 — Execution Sandbox (§53)."""

from __future__ import annotations

SAFE_CODE = '''
def transform(row):
    row["phone_norm"] = "".join(ch for ch in row["phone"] if ch.isdigit())
    return row
'''

IMPORT_CODE = '''
import os
def transform(row):
    return row
'''

EXEC_CODE = '''
def transform(row):
    exec("x=1")
    return row
'''

DUNDER_CODE = '''
def transform(row):
    return row.__class__
'''

NO_TRANSFORM = '''
def helper(row):
    return row
'''


def test_inspect_accepts_safe_code():
    from app.modules import sandbox

    r = sandbox.inspect_code(SAFE_CODE)
    assert r["safe"] is True
    assert r["defines_transform"] is True
    assert r["violations"] == []


def test_inspect_rejects_import():
    from app.modules import sandbox

    r = sandbox.inspect_code(IMPORT_CODE)
    assert r["safe"] is False
    assert any("import" in v for v in r["violations"])


def test_inspect_rejects_exec_and_dunder():
    from app.modules import sandbox

    assert any("exec" in v for v in sandbox.inspect_code(EXEC_CODE)["violations"])
    assert any("dunder" in v for v in sandbox.inspect_code(DUNDER_CODE)["violations"])


def test_inspect_requires_transform():
    from app.modules import sandbox

    r = sandbox.inspect_code(NO_TRANSFORM)
    assert r["safe"] is False
    assert any("transform" in v for v in r["violations"])


def test_run_unsafe_code_is_not_executed():
    from app.modules import sandbox

    r = sandbox.run(IMPORT_CODE)
    assert r["executed"] is False
    assert r["stage"] == "static_inspection"


def test_run_safe_code_produces_diff():
    from app.modules import sandbox

    r = sandbox.run(SAFE_CODE)
    assert r["executed"] is True
    assert r["test_rows"] == len(sandbox.SANDBOX_TEST_ROWS)
    # T001 telefone com pontuação -> phone_norm só dígitos.
    t1 = next(d for d in r["diffs"] if d["record_id"] == "T001")
    changed = {c["field"]: c["after"] for c in t1["changes"]}
    assert changed.get("phone_norm") == "27999991234"


def test_run_catches_row_errors_without_crashing():
    from app.modules import sandbox

    code = '''
def transform(row):
    return row["nao_existe"].upper()
'''
    r = sandbox.run(code)
    assert r["executed"] is True
    assert r["errors"] == len(sandbox.SANDBOX_TEST_ROWS)  # todas as linhas falham, mas capturado

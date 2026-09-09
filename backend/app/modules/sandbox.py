"""Execution Sandbox (Blueprint §53).

Código gerado (por LLM ou humano) JAMAIS roda diretamente sobre a base de
evidência. O fluxo é:

    código → inspeção estática → sandbox → dataset de teste → diff → aprovação
    → (só então) promoção a regra registrada, que roda sobre dados reais.

Este módulo cobre até o diff sobre um DATASET DE TESTE sintético (nunca dados do
caso). A execução sobre dados reais permanece restrita ao motor de regras
registradas (determinístico e versionado, §52) — código arbitrário não é
promovido automaticamente.

Aviso honesto: a inspeção por AST + globals restritos é defesa em profundidade,
não um limite de segurança equivalente a isolamento de SO. Em produção, a
execução ocorreria em contêiner/seccomp. Aqui o objetivo é validar candidatos
com segurança razoável e mostrar o efeito antes de qualquer promoção.
"""

from __future__ import annotations

import ast
import copy
import re
import signal

# Dataset de TESTE sintético (§53) — nunca dados do caso. Fixo e fictício.
SANDBOX_TEST_ROWS = [
    {"record_id": "T001", "phone": "(27) 99999-1234", "cpf": "111.222.333-44", "amount": "1500.00"},
    {"record_id": "T002", "phone": "27999991234", "cpf": "222.333.444-55", "amount": "2500,50"},
    {"record_id": "T003", "phone": "+55 27 98888-0000", "cpf": "N/A", "amount": "0"},
    {"record_id": "T004", "phone": "", "cpf": "-1", "amount": "999999"},
]

_FORBIDDEN_CALLS = {
    "eval", "exec", "open", "compile", "__import__", "input", "globals",
    "locals", "vars", "getattr", "setattr", "delattr", "memoryview",
    "breakpoint", "help", "dir",
}
_FORBIDDEN_NAMES = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "importlib",
    "ctypes", "builtins", "open", "__builtins__", "globals", "connect",
}

# Builtins seguros disponíveis dentro do sandbox.
_SAFE_BUILTINS = {
    n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
    for n in ("len", "str", "int", "float", "round", "abs", "min", "max", "sum",
              "sorted", "list", "dict", "set", "tuple", "enumerate", "range",
              "zip", "map", "filter", "any", "all", "bool", "isinstance", "print")
}


class SandboxViolation(Exception):
    pass


def inspect_code(code: str) -> dict:
    """Inspeção estática por AST (§53). Retorna violações e se é seguro."""
    violations: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"safe": False, "violations": [f"erro de sintaxe: {exc}"],
                "defines_transform": False}

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            violations.append("import proibido (código não pode importar módulos)")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            violations.append(f"acesso a atributo dunder proibido: {node.attr}")
        elif isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            violations.append(f"nome proibido: {node.id}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _FORBIDDEN_CALLS:
                violations.append(f"chamada proibida: {node.func.id}()")

    defines = any(
        isinstance(n, ast.FunctionDef) and n.name == "transform"
        for n in ast.walk(tree)
    )
    if not defines:
        violations.append("o código deve definir uma função transform(row).")

    return {"safe": len(violations) == 0, "violations": sorted(set(violations)),
            "defines_transform": defines}


def _run_transform(code: str, rows: list[dict], timeout_s: int = 2) -> list[dict]:
    sandbox_globals = {"__builtins__": _SAFE_BUILTINS, "re": re}
    exec(compile(code, "<sandbox>", "exec"), sandbox_globals)  # noqa: S102
    transform = sandbox_globals.get("transform")
    if not callable(transform):
        raise SandboxViolation("transform não é uma função")

    results = []

    def _alarm(_s, _f):
        raise TimeoutError("execução excedeu o tempo limite do sandbox")

    armed = False
    try:
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(timeout_s)
        armed = True
    except (ValueError, AttributeError):
        armed = False  # não é main thread: seguimos sem alarme (dataset pequeno)

    try:
        for row in rows:
            try:
                out = transform(copy.deepcopy(row))
                results.append({"input": row, "output": out, "error": None})
            except Exception as exc:  # noqa: BLE001
                results.append({"input": row, "output": None, "error": str(exc)})
    finally:
        if armed:
            signal.alarm(0)
    return results


def _diff(input_row: dict, output) -> list[dict]:
    if not isinstance(output, dict):
        return [{"field": "<retorno>", "before": "dict", "after": type(output).__name__}]
    changes = []
    for k in sorted(set(input_row) | set(output)):
        before, after = input_row.get(k), output.get(k)
        if before != after:
            changes.append({"field": k, "before": before, "after": after})
    return changes


def run(code: str) -> dict:
    """Inspeciona e, se seguro, executa sobre o dataset de teste, com diff (§53)."""
    report = inspect_code(code)
    if not report["safe"]:
        return {"stage": "static_inspection", "executed": False, **report,
                "message": "Recusado na inspeção estática. Sandbox não executado."}
    try:
        runs = _run_transform(code, SANDBOX_TEST_ROWS)
    except (SandboxViolation, TimeoutError) as exc:
        return {"stage": "sandbox", "executed": False, "safe": True, "violations": [],
                "message": f"Falha no sandbox: {exc}"}

    diffs = []
    errors = 0
    for r in runs:
        if r["error"]:
            errors += 1
            diffs.append({"record_id": r["input"].get("record_id"), "error": r["error"]})
        else:
            diffs.append({"record_id": r["input"].get("record_id"),
                          "changes": _diff(r["input"], r["output"])})
    return {
        "stage": "diff",
        "executed": True,
        "safe": True,
        "test_rows": len(SANDBOX_TEST_ROWS),
        "errors": errors,
        "diffs": diffs,
        "message": ("Execução em dataset de TESTE (nunca dados do caso). Promover à "
                    "produção exige registrar uma regra versionada (§52) — código "
                    "arbitrário não roda sobre a base de evidência (§53)."),
    }

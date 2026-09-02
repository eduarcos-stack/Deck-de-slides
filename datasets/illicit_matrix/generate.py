"""Gerador do dataset demonstrador "Illicit Matrix" (Blueprint §82).

Produz 72 registros SINTÉTICOS com ground truth conhecido, servindo
simultaneamente como red-team dataset (§66) e gold dataset (§67). É
determinístico (seed fixa) para garantir reprodutibilidade (§64).

Armadilhas embutidas propositalmente (§66):
  - dois "Carlos Eduardo Silva" homônimos, com CPF e nascimento CONFLITANTES
    (teste de false merge — §24, §85);
  - duplicatas técnicas (mesmo evento reimportado);
  - eventos repetidos LEGÍTIMOS (mesma pessoa, transações distintas);
  - missingness com sentinelas ambíguas (§15);
  - múltiplos formatos de telefone e de timestamp;
  - dois timestamps ambíguos que um parser ingênuo joga para meia-noite (§89).

IMPORTANTE: todos os nomes, CPFs, valores e empresas são fictícios.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
SEED = 20240815
random.seed(SEED)

FIELDS = [
    "record_id", "event_id", "timestamp", "name", "cpf", "dob", "phone",
    "email", "company", "account", "counterparty", "amount", "currency",
    "channel", "city", "device_id", "source_system", "notes",
]

# Duas identidades homônimas com identificadores discriminantes conflitantes.
CARLOS_A = {
    "name": "Carlos Eduardo Silva", "cpf": "111.222.333-44", "dob": "14/05/1980",
    "company": "Nexus Log LTDA", "city": "Vila Velha",
}
CARLOS_B = {
    "name": "Carlos Eduardo Silva", "cpf": "999.888.777-66", "dob": "20/09/1982",
    "company": "Vanguarda Fomento", "city": "Serra",
}
OTHERS = [
    {"name": "Marina Alves Costa", "cpf": "222.333.444-55", "dob": "03/11/1979",
     "company": "Nexus Log LTDA", "city": "Vitória"},
    {"name": "Rafael Menezes", "cpf": "333.444.555-66", "dob": "27/02/1990",
     "company": "Vanguarda Fomento", "city": "Cariacica"},
    {"name": "Juliana Prado", "cpf": "444.555.666-77", "dob": "19/07/1985",
     "company": "Órion Serviços", "city": "Vila Velha"},
]

PHONE_FORMATS = [
    lambda: "(27) 99999-1234",
    lambda: "27999991234",
    lambda: "+55 27 99999-1234",
    lambda: "27 9 9999 1234",
]
COUNTERPARTIES = ["Órion Serviços", "BR Trade", "Delta Comercial", "Sigma ME"]
CHANNELS = ["TED", "PIX", "boleto", "saque"]


def _phone() -> str:
    return random.choice(PHONE_FORMATS)()


def _amount() -> str:
    return f"{random.randint(1500, 90000)}.{random.randint(0, 99):02d}"


def _ts(day: int, hour: int, minute: int, fmt: int) -> str:
    """Gera timestamp em um de três padrões (§13 — 3 padrões de timestamp)."""
    if fmt == 0:  # ISO com offset
        return f"2024-08-{day:02d}T{hour:02d}:{minute:02d}:00-03:00"
    if fmt == 1:  # BR com offset
        return f"{day:02d}/08/2024 {hour:02d}:{minute:02d} -03:00"
    return f"{day:02d}/08/2024 {hour:02d}h{minute:02d}"  # BR informal


def build() -> list[dict]:
    rows: list[dict] = []
    rid = 0

    def add(identity: dict, event_id: str, **over) -> dict:
        nonlocal rid
        rid += 1
        base = {
            "record_id": f"R{rid:03d}",
            "event_id": event_id,
            "timestamp": _ts(random.randint(10, 20), random.randint(8, 23),
                             random.randint(0, 59), random.randint(0, 2)),
            "name": identity["name"],
            "cpf": identity["cpf"],
            "dob": identity["dob"],
            "phone": _phone(),
            "email": (identity["name"].split()[0].lower() + "@mail.test"),
            "company": identity["company"],
            "account": f"{random.randint(10000, 99999)}-{random.randint(0,9)}",
            "counterparty": random.choice(COUNTERPARTIES),
            "amount": _amount(),
            "currency": "BRL",
            "channel": random.choice(CHANNELS),
            "city": identity["city"],
            "device_id": f"DEV-{random.randint(100, 999)}",
            "source_system": random.choice(["Nexus", "Vanguarda"]),
            "notes": "",
        }
        base.update(over)
        rows.append(base)
        return base

    # Carlos A — 14 eventos legítimos (§26).
    for i in range(14):
        add(CARLOS_A, f"EVT-A{i:03d}")
    # Carlos B — 5 eventos legítimos, empresa diferente (§26).
    for i in range(5):
        add(CARLOS_B, f"EVT-B{i:03d}")
    # Demais indivíduos — 36 eventos (total canônico do caso = 72, §13/§82).
    for i in range(36):
        add(random.choice(OTHERS), f"EVT-C{i:03d}")

    # --- Armadilhas controladas ---------------------------------------------
    gt_technical_dupes = []
    # 4 duplicatas TÉCNICAS: reimportação do MESMO evento (§20). Cópia integral
    # do registro de origem, divergindo apenas em campo não-core (notes),
    # como ocorre num reimport de lote — diferente de divergência real.
    for i in range(4):
        rid += 1
        src = rows[i]
        dup = dict(src)
        dup["record_id"] = f"R{rid:03d}"
        dup["notes"] = "reimport lote 2"
        dup["source_system"] = "Nexus"
        rows.append(dup)
        gt_technical_dupes.append((src["record_id"], dup["record_id"]))

    # 3 eventos repetidos LEGÍTIMOS: mesma pessoa/dia, valores distintos (§20).
    for i in range(3):
        add(CARLOS_A, f"EVT-AR{i:03d}", notes="parcela recorrente")

    # 8 registros com missingness sentinela ambígua (§15).
    sentinels = ["", "N/A", "NI", "não informado", "não consta", "-1", "999999", ""]
    gt_missing = []
    for s in sentinels:
        r = add(random.choice(OTHERS), f"EVT-M{random.randint(0,999):03d}",
                cpf=s, notes="cadastro incompleto")
        gt_missing.append(r["record_id"])

    # 2 timestamps ambíguos que um parser ingênuo converte para meia-noite (§89).
    gt_midnight = []
    for i in range(2):
        r = add(CARLOS_A, f"EVT-T{i:03d}", timestamp="15/08/2024 24:00",
                notes="hora ambigua (24:00)")
        gt_midnight.append(r["record_id"])

    return rows


def main() -> None:
    rows = build()
    csv_path = HERE / "illicit_matrix.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    ground_truth = {
        "description": "Ground truth do dataset sintético Illicit Matrix (Blueprint §82).",
        "total_records": len(rows),
        "distinct_entities": {
            "carlos_a": {"identity": CARLOS_A, "note": "14 eventos legítimos + repetições"},
            "carlos_b": {"identity": CARLOS_B, "note": "5 eventos, empresa distinta"},
            "expected_decision_carlos_a_vs_b": "NON-MATCH",
            "rationale": "Nome idêntico (sim=1.00), mas CPF e nascimento conflitantes "
                         "(dois identificadores altamente discriminantes) — §24, §85.",
        },
        "technical_duplicates": {"count": 4, "pairs": None,
                                 "note": "mesmo event_id reimportado (lote 2)"},
        "legitimate_repeated_events": {"count": 3, "note": "parcelas recorrentes de Carlos A"},
        "missing_sentinel_records": {"count": 8},
        "temporal_anomalies": {"count": 2, "note": "timestamp 24:00 — risco de colapso p/ meia-noite (§89)"},
        "seed": SEED,
    }
    (HERE / "ground_truth.json").write_text(
        json.dumps(ground_truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Gerados {len(rows)} registros em {csv_path.name}")
    print(f"Ground truth em ground_truth.json")


if __name__ == "__main__":
    main()

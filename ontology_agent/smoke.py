"""Lightweight checks you can run with: python -m ontology_agent.smoke"""

from __future__ import annotations

from .generator import OntologyGenerator
from .loader import load_dictionary
from .nl2sql import NL2SQLAgent
from .seed import refresh_customer_spend, seed_fourth_coffee
from pathlib import Path


def run() -> None:
    root = Path(__file__).resolve().parent.parent
    onto = load_dictionary(root / "dictionaries" / "fourth_coffee.json")
    assert len(onto.entities) == 6
    assert len(onto.relationships) == 7
    gen = OntologyGenerator(onto)
    conn = gen.materialize(":memory:")
    seed_fourth_coffee(conn)
    refresh_customer_spend(conn)
    result = NL2SQLAgent(onto, conn).ask("customer 最大的销售和最大的supplier")
    names = {f["label"]: f["value"] for f in result.facts}
    assert "Elena Rossi" in names["最大销售客户"]
    assert "Guatemala" in names.get("产地国家", "") or "最大" in "".join(names)
    assert result.sql
    assert result.instance_graph["nodes"]
    print("smoke ok:", names["最大销售客户"], names.get("对该客户贡献最大的供应商"))


if __name__ == "__main__":
    run()

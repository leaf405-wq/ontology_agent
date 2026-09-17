from __future__ import annotations

import sqlite3
from collections import deque
from dataclasses import dataclass
from typing import Any

from .generator import OntologyGenerator, qident
from .models import Entity, Ontology, Property


SYNONYMS = {
    "customer": ["customer", "customers", "顾客", "客户", "会员"],
    "order": ["order", "orders", "订单", "销售", "销售额", "消费"],
    "product": ["product", "products", "产品", "商品", "咖啡"],
    "store": ["store", "stores", "门店", "店铺", "商店"],
    "supplier": ["supplier", "suppliers", "供应商", "供货商"],
    "shipment": ["shipment", "shipments", "发货", "物流", "货运"],
}

MAX_WORDS = ["最大", "最高", "最多", "top", "largest", "max", "highest", "biggest"]
MIN_WORDS = ["最小", "最低", "最少", "min", "lowest", "smallest"]
LIST_WORDS = ["列出", "所有", "list", "show", "all", "哪些"]


@dataclass
class QueryResult:
    question: str
    interpretation: str
    sql: list[str]
    facts: list[dict[str, Any]]
    subgraph: dict[str, Any]
    highlight_entities: list[str]
    highlight_relationships: list[str]


class NL2SQLAgent:
    def __init__(self, ontology: Ontology, db_path: str) -> None:
        self.ontology = ontology
        self.db_path = db_path
        self.schema_graph = OntologyGenerator(ontology).graph_schema()

    def ask(self, question: str) -> QueryResult:
        q = question.strip()
        entities = self._mentioned_entities(q)
        intent = self._intent(q)
        if not entities:
            entities = self._guess_from_measures(q)
        if not entities:
            return self._fallback(q)

        if intent in {"max", "min"} and len(entities) >= 1:
            return self._rank_query(q, entities, intent)
        if intent == "list":
            return self._list_query(q, entities)
        return self._rank_query(q, entities, "max" if any(w in q.lower() for w in MAX_WORDS) else "list")

    def _mentioned_entities(self, q: str) -> list[str]:
        found: list[str] = []
        low = q.lower()
        for entity in self.ontology.entities:
            keys = SYNONYMS.get(entity.id, []) + [entity.id, entity.name.lower()]
            if any(k.lower() in low or k in q for k in keys):
                found.append(entity.id)
        # 销售 often maps to both order and customer spend
        if "销售" in q and "customer" not in found:
            found.insert(0, "customer")
        if "销售" in q and "order" not in found:
            found.append("order")
        return list(dict.fromkeys(found))

    def _guess_from_measures(self, q: str) -> list[str]:
        hits = []
        for entity in self.ontology.entities:
            for prop in entity.properties:
                if prop.name.lower() in q.lower() or prop.column in q.lower():
                    hits.append(entity.id)
        return list(dict.fromkeys(hits))

    def _intent(self, q: str) -> str:
        low = q.lower()
        if any(w in q or w in low for w in MAX_WORDS):
            return "max"
        if any(w in q or w in low for w in MIN_WORDS):
            return "min"
        if any(w in q or w in low for w in LIST_WORDS):
            return "list"
        return "explore"

    def _rank_query(self, question: str, entity_ids: list[str], intent: str) -> QueryResult:
        direction = "DESC" if intent == "max" else "ASC"
        label = "最大" if intent == "max" else "最小"
        sqls: list[str] = []
        facts: list[dict[str, Any]] = []
        used_entities = set(entity_ids)
        used_rels: set[str] = set()

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            for eid in entity_ids:
                entity = self.ontology.entity(eid)
                measure = self._pick_measure(entity, question)
                table = qident(entity.table)
                pk = qident(entity.pk.column)
                measure_col = qident(measure.column)
                has_name = any(p.column == "name" for p in entity.properties)
                name_expr = qident("name") if has_name else pk
                sql = (
                    f"SELECT {pk} AS id, {name_expr} AS name, {measure_col} AS metric "
                    f"FROM {table} ORDER BY {measure_col} {direction} LIMIT 1"
                )
                sqls.append(sql)
                row = conn.execute(sql).fetchone()
                if row:
                    facts.append(
                        {
                            "entity": entity.name,
                            "id": row["id"],
                            "name": row["name"],
                            "metric": measure.name,
                            "value": row["metric"],
                            "unit": measure.unit,
                            "meaning": f"{label}{entity.name}（按 {measure.name}）",
                        }
                    )
            # If customer + supplier: also compute supplier that supplied the most $ to top customer
            if "customer" in entity_ids and "supplier" in entity_ids:
                extra_sql, extra_fact, extra_ents, extra_rels = self._customer_supplier_bridge(conn, direction)
                if extra_sql:
                    sqls.append(extra_sql)
                if extra_fact:
                    facts.append(extra_fact)
                used_entities.update(extra_ents)
                used_rels.update(extra_rels)
            else:
                used_rels.update(self._path_rel_ids(entity_ids))
                used_entities.update(self._entities_on_paths(entity_ids))
        finally:
            conn.close()

        interpretation = (
            f"NL2SQL：在 {', '.join(entity_ids)} 上按度量字段取{label}值，"
            "并裁剪经过这些实体的本体子图。"
        )
        return QueryResult(
            question=question,
            interpretation=interpretation,
            sql=sqls,
            facts=facts,
            subgraph=self._subgraph(used_entities, used_rels),
            highlight_entities=sorted(used_entities),
            highlight_relationships=sorted(used_rels),
        )

    def _customer_supplier_bridge(self, conn: sqlite3.Connection, direction: str) -> tuple[str, dict | None, set[str], set[str]]:
        sql = """
        SELECT s.supplier_id AS id, s.name AS name,
               ROUND(SUM(ocp.line_amount), 2) AS metric
        FROM customer c
        JOIN "order" o ON o.customer_id = c.customer_id
        JOIN order_contains_product ocp ON ocp.order_id = o.order_id
        JOIN product p ON p.product_id = ocp.product_id
        JOIN supplier s ON s.supplier_id = p.supplier_id
        WHERE c.customer_id = (
            SELECT customer_id FROM customer ORDER BY total_spend DESC LIMIT 1
        )
        GROUP BY s.supplier_id, s.name
        ORDER BY metric %s
        LIMIT 1
        """ % direction
        row = conn.execute(sql).fetchone()
        fact = None
        if row:
            fact = {
                "entity": "Supplier",
                "id": row["id"],
                "name": row["name"],
                "metric": "sales_to_top_customer",
                "value": row["metric"],
                "unit": "USD",
                "meaning": "对销售额最大顾客供货金额最高的供应商",
            }
        rels = {
            "customer_places_order",
            "order_contains_product",
            "product_sourced_from_supplier",
        }
        return sql.strip(), fact, {"customer", "order", "product", "supplier"}, rels

    def _list_query(self, question: str, entity_ids: list[str]) -> QueryResult:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        sqls = []
        facts = []
        try:
            for eid in entity_ids[:2]:
                entity = self.ontology.entity(eid)
                cols = ", ".join(qident(p.column) for p in entity.properties[:6])
                sql = f"SELECT {cols} FROM {qident(entity.table)} LIMIT 8"
                sqls.append(sql)
                for row in conn.execute(sql).fetchall():
                    facts.append(
                        {
                            "entity": entity.name,
                            "id": row[0],
                            "name": row[1] if len(row) > 1 else row[0],
                            "metric": "preview",
                            "value": dict(row),
                            "meaning": f"{entity.name} 实例预览",
                        }
                    )
        finally:
            conn.close()
        rels = self._path_rel_ids(entity_ids)
        ents = self._entities_on_paths(entity_ids)
        return QueryResult(
            question=question,
            interpretation=f"列出 {', '.join(entity_ids)} 的实例，并高亮相关本体路径。",
            sql=sqls,
            facts=facts,
            subgraph=self._subgraph(ents, rels),
            highlight_entities=sorted(ents),
            highlight_relationships=sorted(rels),
        )

    def _fallback(self, question: str) -> QueryResult:
        return QueryResult(
            question=question,
            interpretation="未能识别实体。请包含 Customer / Order / Product / Store / Supplier / Shipment 或其中文同义词。",
            sql=[],
            facts=[],
            subgraph=self.schema_graph,
            highlight_entities=[],
            highlight_relationships=[],
        )

    def _pick_measure(self, entity: Entity, question: str) -> Property:
        q = question.lower()
        for prop in entity.properties:
            if prop.name.lower() in q or prop.column in q:
                return prop
        if entity.id == "customer" and ("销售" in question or "spend" in q or "sales" in q):
            return next(p for p in entity.properties if p.column == "total_spend")
        if entity.id == "supplier" and ("销售" in question or "sales" in q):
            # rating as default; bridge query overrides
            rated = next((p for p in entity.properties if p.column == "rating"), None)
            if rated:
                return rated
        measures = entity.measure_props()
        return measures[0] if measures else entity.properties[-1]

    def _path_rel_ids(self, entity_ids: list[str]) -> set[str]:
        if len(entity_ids) < 2:
            return {r.id for e in entity_ids for r, _ in self.ontology.neighbors(e)}
        used: set[str] = set()
        for a, b in zip(entity_ids, entity_ids[1:]):
            used.update(self._bfs_rels(a, b))
        if not used and len(entity_ids) >= 2:
            used.update(self._bfs_rels(entity_ids[0], entity_ids[-1]))
        return used

    def _entities_on_paths(self, entity_ids: list[str]) -> set[str]:
        nodes = set(entity_ids)
        for a in entity_ids:
            for b in entity_ids:
                if a == b:
                    continue
                rels = self._bfs_rels(a, b)
                for rid in rels:
                    rel = next(r for r in self.ontology.relationships if r.id == rid)
                    nodes.add(rel.from_id)
                    nodes.add(rel.to_id)
        return nodes

    def _bfs_rels(self, start: str, goal: str) -> set[str]:
        q = deque([(start, [])])
        seen = {start}
        while q:
            node, path = q.popleft()
            if node == goal and path:
                return set(path)
            for rel, nxt in self.ontology.neighbors(node):
                if nxt in seen:
                    continue
                seen.add(nxt)
                q.append((nxt, path + [rel.id]))
        return set()

    def _subgraph(self, entity_ids: set[str], rel_ids: set[str]) -> dict[str, Any]:
        nodes = [n for n in self.schema_graph["nodes"] if n["id"] in entity_ids]
        edges = [
            e
            for e in self.schema_graph["edges"]
            if e["id"] in rel_ids or (e["from"] in entity_ids and e["to"] in entity_ids)
        ]
        if not nodes:
            return self.schema_graph
        return {"nodes": nodes, "edges": edges}

from __future__ import annotations

import json
from pathlib import Path

from .models import Ontology, Relationship


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class OntologyGenerator:
    def __init__(self, ontology: Ontology) -> None:
        self.ontology = ontology

    def ddl(self) -> list[str]:
        statements = ["PRAGMA foreign_keys = ON;"]
        for entity in self.ontology.entities:
            cols = []
            for prop in entity.properties:
                extras = " PRIMARY KEY" if prop.identifier else ""
                cols.append(f"  {qident(prop.column)} {prop.sql_type}{extras}")
            for rel in self.ontology.relationships:
                fk = self._fk_column(rel, entity.id)
                if fk:
                    cols.append(f"  {qident(fk)} TEXT")
            statements.append(
                f"CREATE TABLE IF NOT EXISTS {qident(entity.table)} (\n" + ",\n".join(cols) + "\n);"
            )
        for rel in self.ontology.relationships:
            if not rel.is_m2m:
                continue
            extra = [f"  {qident(a.column)} {a.sql_type}" for a in rel.attributes]
            statements.append(
                f"CREATE TABLE IF NOT EXISTS {qident(rel.junction_table)} (\n"
                f"  {qident(rel.from_id + '_id')} TEXT,\n"
                f"  {qident(rel.to_id + '_id')} TEXT"
                + (",\n" + ",\n".join(extra) if extra else "")
                + f",\n  PRIMARY KEY ({qident(rel.from_id + '_id')}, {qident(rel.to_id + '_id')})\n);"
            )
        return statements

    def graph_schema(self) -> dict:
        nodes = [
            {
                "id": e.id,
                "label": e.name,
                "icon": e.icon,
                "color": e.color,
                "title": e.description,
                "group": "entity",
                "properties": [p.name for p in e.properties],
            }
            for e in self.ontology.entities
        ]
        edges = [
            {
                "id": r.id,
                "from": r.from_id,
                "to": r.to_id,
                "label": r.name,
                "title": f"{r.name} ({r.cardinality})",
                "arrows": "to",
            }
            for r in self.ontology.relationships
        ]
        return {"nodes": nodes, "edges": edges}

    def write(self, out_dir: str | Path) -> Path:
        dest = Path(out_dir)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "ontology.json").write_text(
            json.dumps(self.ontology.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (dest / "schema.sql").write_text("\n\n".join(self.ddl()) + "\n", encoding="utf-8")
        (dest / "graph.json").write_text(
            json.dumps(self.graph_schema(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return dest

    def _fk_column(self, rel: Relationship, entity_id: str) -> str | None:
        if rel.is_m2m:
            return None
        if rel.cardinality in {"one-to-many"} and rel.to_id == entity_id:
            return f"{rel.from_id}_id"
        if rel.cardinality in {"many-to-one", "one-to-one"} and rel.from_id == entity_id:
            return f"{rel.to_id}_id"
        if rel.cardinality == "one-to-many" and rel.from_id == entity_id:
            return None
        return None

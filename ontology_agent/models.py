from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


PYTHON_TYPES = {
    "string": "TEXT",
    "integer": "INTEGER",
    "decimal": "REAL",
    "double": "REAL",
    "date": "TEXT",
    "datetime": "TEXT",
    "boolean": "INTEGER",
    "enum": "TEXT",
}


@dataclass
class Property:
    name: str
    type: str = "string"
    identifier: bool = False
    unit: str | None = None
    values: list[str] = field(default_factory=list)
    description: str = ""
    measure: bool = False

    @property
    def column(self) -> str:
        return camel_to_snake(self.name)

    @property
    def sql_type(self) -> str:
        return PYTHON_TYPES.get(self.type, "TEXT")


@dataclass
class RelAttribute:
    name: str
    type: str = "string"

    @property
    def column(self) -> str:
        return camel_to_snake(self.name)

    @property
    def sql_type(self) -> str:
        return PYTHON_TYPES.get(self.type, "TEXT")


@dataclass
class Entity:
    id: str
    name: str
    description: str = ""
    icon: str = "●"
    color: str = "#0078D4"
    properties: list[Property] = field(default_factory=list)

    @property
    def table(self) -> str:
        return self.id

    @property
    def pk(self) -> Property:
        for prop in self.properties:
            if prop.identifier:
                return prop
        return self.properties[0]

    def measure_props(self) -> list[Property]:
        measured = [p for p in self.properties if p.measure]
        if measured:
            return measured
        return [p for p in self.properties if p.type in {"decimal", "double", "integer"} and not p.identifier]


@dataclass
class Relationship:
    id: str
    name: str
    from_id: str
    to_id: str
    cardinality: str = "many-to-one"
    description: str = ""
    attributes: list[RelAttribute] = field(default_factory=list)

    @property
    def junction_table(self) -> str:
        return self.id

    @property
    def is_m2m(self) -> bool:
        return self.cardinality == "many-to-many"


@dataclass
class Ontology:
    name: str
    description: str = ""
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    def entity(self, entity_id: str) -> Entity:
        for item in self.entities:
            if item.id == entity_id or item.name.lower() == entity_id.lower():
                return item
        raise KeyError(entity_id)

    def neighbors(self, entity_id: str) -> list[tuple[Relationship, str]]:
        out: list[tuple[Relationship, str]] = []
        for rel in self.relationships:
            if rel.from_id == entity_id:
                out.append((rel, rel.to_id))
            elif rel.to_id == entity_id:
                out.append((rel, rel.from_id))
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "entities": [
                {
                    "id": e.id,
                    "name": e.name,
                    "description": e.description,
                    "icon": e.icon,
                    "color": e.color,
                    "table": e.table,
                    "properties": [
                        {
                            "name": p.name,
                            "column": p.column,
                            "type": p.type,
                            "identifier": p.identifier,
                            "unit": p.unit,
                            "values": p.values,
                            "description": p.description,
                            "measure": p.measure,
                        }
                        for p in e.properties
                    ],
                }
                for e in self.entities
            ],
            "relationships": [
                {
                    "id": r.id,
                    "name": r.name,
                    "from": r.from_id,
                    "to": r.to_id,
                    "cardinality": r.cardinality,
                    "description": r.description,
                    "junction": r.junction_table if r.is_m2m else None,
                    "attributes": [{"name": a.name, "type": a.type} for a in r.attributes],
                }
                for r in self.relationships
            ],
        }


def camel_to_snake(name: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and (not name[i - 1].isupper() or (i + 1 < len(name) and name[i + 1].islower())):
            out.append("_")
        out.append(ch.lower())
    return "".join(out)

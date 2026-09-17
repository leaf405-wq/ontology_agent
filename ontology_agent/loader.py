from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import Entity, Ontology, Property, RelAttribute, Relationship


def load_dictionary(path: str | Path) -> Ontology:
    raw_path = Path(path)
    text = raw_path.read_text(encoding="utf-8")
    suffix = raw_path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    else:
        data = parse_yaml(text)
    return ontology_from_dict(data)


def ontology_from_dict(data: dict[str, Any]) -> Ontology:
    entities = []
    for item in data.get("entities") or data.get("entityTypes") or []:
        props = [
            Property(
                name=p["name"],
                type=p.get("type", "string"),
                identifier=bool(p.get("identifier") or p.get("isIdentifier")),
                unit=p.get("unit"),
                values=list(p.get("values") or []),
                description=str(p.get("description") or ""),
                measure=bool(p.get("measure")),
            )
            for p in item.get("properties") or []
        ]
        entities.append(
            Entity(
                id=item["id"],
                name=item.get("name") or item["id"].title(),
                description=str(item.get("description") or ""),
                icon=str(item.get("icon") or "●"),
                color=str(item.get("color") or "#0078D4"),
                properties=props,
            )
        )
    relationships = []
    for item in data.get("relationships") or []:
        attrs = [
            RelAttribute(name=a["name"], type=a.get("type", "string"))
            for a in item.get("attributes") or []
        ]
        relationships.append(
            Relationship(
                id=item.get("id") or f"{item['from']}_{item['name']}_{item['to']}",
                name=item["name"],
                from_id=item.get("from") or item.get("from_id"),
                to_id=item.get("to") or item.get("to_id"),
                cardinality=item.get("cardinality", "many-to-one"),
                description=str(item.get("description") or ""),
                attributes=attrs,
            )
        )
    return Ontology(
        name=data.get("name") or "Untitled Ontology",
        description=str(data.get("description") or ""),
        entities=entities,
        relationships=relationships,
    )


def parse_yaml(text: str) -> Any:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except Exception:
        return _MiniYaml(text).parse()


class _MiniYaml:
    """Indent-based YAML subset: maps, lists, scalars, flow []/{}."""

    def __init__(self, text: str) -> None:
        self.lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        self.i = 0

    def parse(self) -> Any:
        return self._block(0)

    def _indent(self, line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def _block(self, indent: int) -> Any:
        if self.i >= len(self.lines):
            return {}
        line = self.lines[self.i]
        if line.lstrip().startswith("- "):
            return self._list(indent)
        return self._map(indent)

    def _map(self, indent: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        while self.i < len(self.lines):
            line = self.lines[self.i]
            cur = self._indent(line)
            if cur < indent:
                break
            if cur > indent:
                raise ValueError(f"Bad indent: {line}")
            if line.lstrip().startswith("- "):
                break
            key, _, rest = line.lstrip().partition(":")
            rest = rest.strip()
            self.i += 1
            if rest == "" or rest == "|":
                if self.i < len(self.lines) and self._indent(self.lines[self.i]) > cur:
                    result[key] = self._block(self._indent(self.lines[self.i]))
                else:
                    result[key] = ""
            else:
                result[key] = self._scalar(rest)
        return result

    def _list(self, indent: int) -> list[Any]:
        items: list[Any] = []
        while self.i < len(self.lines):
            line = self.lines[self.i]
            cur = self._indent(line)
            if cur < indent:
                break
            if not line.lstrip().startswith("- "):
                break
            payload = line.lstrip()[2:].strip()
            self.i += 1
            if payload == "":
                items.append(self._block(cur + 2) if self.i < len(self.lines) else {})
            elif ":" in payload and not payload.startswith("{") and not payload.startswith("["):
                key, _, rest = payload.partition(":")
                obj: dict[str, Any] = {key.strip(): self._scalar(rest.strip()) if rest.strip() else ""}
                child_indent = cur + 2
                while self.i < len(self.lines):
                    nxt = self.lines[self.i]
                    ni = self._indent(nxt)
                    if ni < child_indent or nxt.lstrip().startswith("- "):
                        break
                    if ni == child_indent and ":" in nxt and not nxt.lstrip().startswith("- "):
                        k, _, r = nxt.lstrip().partition(":")
                        r = r.strip()
                        self.i += 1
                        if r == "":
                            obj[k] = self._block(self._indent(self.lines[self.i])) if self.i < len(self.lines) and self._indent(self.lines[self.i]) > child_indent else ""
                        else:
                            obj[k] = self._scalar(r)
                    else:
                        break
                items.append(obj)
            else:
                items.append(self._scalar(payload))
        return items

    def _scalar(self, raw: str) -> Any:
        if raw in {"true", "True"}:
            return True
        if raw in {"false", "False"}:
            return False
        if raw in {"null", "None", "~"}:
            return None
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            return raw[1:-1]
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            if not inner:
                return []
            return [self._scalar(p.strip()) for p in _split_flow(inner)]
        if raw.startswith("{") and raw.endswith("}"):
            inner = raw[1:-1].strip()
            obj: dict[str, Any] = {}
            if inner:
                for part in _split_flow(inner):
                    k, _, v = part.partition(":")
                    obj[k.strip()] = self._scalar(v.strip())
            return obj
        if re.fullmatch(r"-?\d+", raw):
            return int(raw)
        if re.fullmatch(r"-?\d+\.\d+", raw):
            return float(raw)
        return raw


def _split_flow(inner: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in inner:
        if ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return parts

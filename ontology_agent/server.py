from __future__ import annotations

import argparse
import json
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .generator import OntologyGenerator
from .loader import load_dictionary, ontology_from_dict
from .nl2sql import NL2SQLAgent, QueryResult
from .seed import seed_database

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
GEN = ROOT / "generated"
DB = GEN / "ontology.db"
DEFAULT_DICT = ROOT / "dictionaries" / "fourth_coffee.yaml"


class App:
    def __init__(self) -> None:
        self.dictionary_path = DEFAULT_DICT
        self.reload()

    def reload(self, path: Path | None = None) -> None:
        if path:
            self.dictionary_path = path
        self.ontology = load_dictionary(self.dictionary_path)
        GEN.mkdir(exist_ok=True)
        OntologyGenerator(self.ontology).write(GEN)
        try:
            seed_database(self.ontology, DB)
        except sqlite3.Error as exc:
            print("seed skipped:", exc)
        self.agent = NL2SQLAgent(self.ontology, str(DB))

    def ask(self, question: str) -> dict:
        result = self.agent.ask(question)
        return _result_to_dict(result)


APP: App | None = None


def get_app() -> App:
    global APP
    if APP is None:
        APP = App()
    return APP


def _result_to_dict(result: QueryResult) -> dict:
    app = get_app()
    return {
        "question": result.question,
        "interpretation": result.interpretation,
        "sql": result.sql,
        "facts": result.facts,
        "subgraph": result.subgraph,
        "highlightEntities": result.highlight_entities,
        "highlightRelationships": result.highlight_relationships,
        "fullGraph": OntologyGenerator(app.ontology).graph_schema(),
        "ontology": app.ontology.to_dict(),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        app = get_app()
        if parsed.path == "/api/ontology":
            self._json(
                {
                    "ontology": app.ontology.to_dict(),
                    "graph": OntologyGenerator(app.ontology).graph_schema(),
                }
            )
            return
        if parsed.path == "/api/query":
            q = parse_qs(parsed.query).get("q", [""])[0]
            self._json(app.ask(q))
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8") or "{}")
        app = get_app()
        if parsed.path == "/api/query":
            self._json(app.ask(str(data.get("q") or data.get("question") or "")))
            return
        if parsed.path == "/api/dictionary":
            dest = GEN / "uploaded_dictionary.json"
            dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            app.reload(dest)
            self._json({"ok": True, "name": app.ontology.name, "graph": OntologyGenerator(app.ontology).graph_schema()})
            return
        self.send_error(404)

    def _json(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print("[http]", fmt % args)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Ontology ChatBI  ->  http://{host}:{port}")
    print(f"Dictionary        ->  {get_app().dictionary_path}")
    httpd.serve_forever()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Hand-rolled ontology generator + NL2SQL ChatBI")
    sub = parser.add_subparsers(dest="cmd")
    gen = sub.add_parser("generate", help="Generate schema/graph from a data dictionary")
    gen.add_argument("dictionary", nargs="?", default=str(DEFAULT_DICT))
    gen.add_argument("--out", default=str(GEN))
    ask = sub.add_parser("ask", help="Run one NL query against seeded facts")
    ask.add_argument("question")
    ask.add_argument("--dictionary", default=str(DEFAULT_DICT))
    srv = sub.add_parser("serve", help="Start the HTML prompt website")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8765)
    srv.add_argument("--dictionary", default=str(DEFAULT_DICT))
    args = parser.parse_args(argv)

    if args.cmd == "generate":
        ont = load_dictionary(args.dictionary)
        OntologyGenerator(ont).write(args.out)
        seed_database(ont, Path(args.out) / "ontology.db")
        print(f"Wrote ontology, SQL, graph, and SQLite to {args.out}")
        return
    app = get_app()
    if args.cmd == "ask":
        app.reload(Path(args.dictionary))
        print(json.dumps(app.ask(args.question), ensure_ascii=False, indent=2, default=str))
        return
    app.reload(Path(getattr(args, "dictionary", DEFAULT_DICT)))
    serve(getattr(args, "host", "127.0.0.1"), getattr(args, "port", 8765))


if __name__ == "__main__":
    main()

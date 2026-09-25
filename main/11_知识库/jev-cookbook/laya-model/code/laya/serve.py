"""Serve one preloaded Laya checkpoint on a Jev-compatible local HTTP route."""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from .client import LayaClient


def make_handler(client: LayaClient) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "LayaLocal/0.1"

        def _json(self, status: int, body: dict[str, Any]) -> None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if self.path == "/healthz":
                self._json(200, {"status": "ok", "model": client.model_name, "device": client.device})
                return
            if self.path == "/v1/models":
                self._json(
                    200,
                    {
                        "models": [
                            {
                                "name": client.model_name,
                                "description": "Local Laya typed-decision checkpoint",
                                "release_date": "2026-09-20",
                            }
                        ]
                    },
                )
                return
            self._json(404, {"error": {"message": "not found", "type": "not_found"}})

        def do_POST(self) -> None:
            if self.path != "/v1/systemone":
                self._json(404, {"error": {"message": "not found", "type": "not_found"}})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 4 * 1024 * 1024:
                    raise ValueError("request body must be between 1 byte and 4 MiB")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("request body must be a JSON object")
                if "state" not in body or "questions" not in body or "model" not in body:
                    raise ValueError("required fields: model, state, questions")
                result = client.system_one(body["state"], body["questions"], model=body["model"])
                self._json(200, result)
            except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
                self._json(400, {"error": {"message": str(exc), "type": "invalid_request"}})
            except Exception:
                self.log_error("Laya inference failed")
                self._json(500, {"error": {"message": "inference failed", "type": "server_error"}})

        def log_message(self, fmt: str, *args: Any) -> None:
            print("laya-api: " + fmt % args)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("LAYA_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("LAYA_PORT", "8811")))
    parser.add_argument("--model-dir", default=os.environ.get("LAYA_MODEL_DIR"))
    parser.add_argument("--model-name", default=os.environ.get("LAYA_MODEL_NAME"))
    parser.add_argument("--device", default=os.environ.get("LAYA_DEVICE"))
    args = parser.parse_args()

    # Load once at startup so request latency excludes checkpoint loading.
    client = LayaClient(args.model_dir, model_name=args.model_name, device=args.device)
    server = HTTPServer((args.host, args.port), make_handler(client))
    print(f"Laya ready: model={client.model_name} device={client.device} http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

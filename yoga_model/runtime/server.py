from __future__ import annotations

import argparse
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image

from classifier import YogaClassifier


class Handler(BaseHTTPRequestHandler):
    classifier: YogaClassifier

    def _headers(self, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._headers(204)

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/health":
            self._headers(404)
            self.wfile.write(b'{"error":"not_found"}')
            return
        self._headers()
        self.wfile.write(json.dumps({"status": "ok", "model": "yoga82_efficientnet_b0"}).encode())

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/predict":
            self._headers(404)
            self.wfile.write(b'{"error":"not_found"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 5 * 1024 * 1024:
                raise ValueError("image body must be between 1 byte and 5 MB")
            image = Image.open(io.BytesIO(self.rfile.read(length)))
            selected = parse_qs(parsed.query).get("selected_pose", [None])[0]
            static = parse_qs(parsed.query).get("static", ["0"])[0] == "1"
            result = self.classifier.predict(image, selected, static=static)
            self._headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        except Exception as exc:
            self._headers(400)
            self.wfile.write(json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[classifier] {self.address_string()} {fmt % args}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Local-only HerMotion classifier API")
    parser.add_argument("--checkpoint", default=str(root / "models/best.pt"))
    parser.add_argument("--config", default=str(root / "config/runtime_gate.json"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    Handler.classifier = YogaClassifier(args.checkpoint, args.config)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"HerMotion classifier ready: http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

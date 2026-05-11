import argparse
import json
import os
import queue
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .orchestrator import WritingOrchestrator


STATIC_DIR = Path(__file__).resolve().parent / "web_static"


class WebAppState:
    def __init__(self) -> None:
        self.ui_queue: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        self.orchestrator = WritingOrchestrator(self.ui_queue)
        self.clients: list["queue.Queue[tuple[str, Any]]"] = []
        self.lock = threading.Lock()
        self.dispatcher = threading.Thread(target=self._dispatch_events, daemon=True)
        self.dispatcher.start()

    def _dispatch_events(self) -> None:
        while True:
            event = self.ui_queue.get()
            with self.lock:
                clients = list(self.clients)
            for client in clients:
                client.put(event)

    def add_client(self) -> "queue.Queue[tuple[str, Any]]":
        client: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        with self.lock:
            self.clients.append(client)
        return client

    def remove_client(self, client: "queue.Queue[tuple[str, Any]]") -> None:
        with self.lock:
            if client in self.clients:
                self.clients.remove(client)


class WritingHelperRequestHandler(BaseHTTPRequestHandler):
    app_state: WebAppState

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/app.css":
            self._serve_file(STATIC_DIR / "app.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/app.js":
            self._serve_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        if parsed.path == "/events":
            self._serve_events()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = self._read_json()
        try:
            if parsed.path == "/api/start":
                self.app_state.orchestrator.start_new_task(
                    username=str(payload.get("username", "")),
                    task=str(payload.get("task", "")),
                )
                self._send_json({"ok": True})
            elif parsed.path == "/api/stop":
                self.app_state.orchestrator.stop_streaming()
                self._send_json({"ok": True})
            elif parsed.path == "/api/accept":
                self.app_state.orchestrator.accept_current_text()
                self._send_json({"ok": True})
            elif parsed.path == "/api/continue":
                self.app_state.orchestrator.continue_generation()
                self._send_json({"ok": True})
            elif parsed.path == "/api/apply":
                self.app_state.orchestrator.apply_selected_option(
                    option_id=str(payload.get("option_id", "")),
                    other_mode=str(payload.get("other_mode", "describe_revision")),
                    other_text=str(payload.get("other_text", "")),
                )
                self._send_json({"ok": True})
            elif parsed.path == "/api/export":
                self._send_json({"ok": True, "session": self.app_state.orchestrator.export_session_json()})
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status=500)

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_events(self) -> None:
        client = self.app_state.add_client()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            self.wfile.write(b"event: ready\ndata: {}\n\n")
            self.wfile.flush()
            while True:
                try:
                    event_type, payload = client.get(timeout=15)
                    data = json.dumps(payload, ensure_ascii=False)
                    self.wfile.write(f"event: {event_type}\ndata: {data}\n\n".encode("utf-8"))
                except queue.Empty:
                    self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionError, TimeoutError):
            pass
        finally:
            self.app_state.remove_client(client)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_web_app(host: str = "127.0.0.1", port: int = 8765) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Set it in your environment before launching the app.")
    app_state = WebAppState()
    WritingHelperRequestHandler.app_state = app_state
    server = ThreadingHTTPServer((host, port), WritingHelperRequestHandler)
    url = f"http://{host}:{server.server_address[1]}"
    print(f"Writing Helper web UI running at {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app_state.orchestrator.shutdown()
        server.server_close()
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Writing Helper web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run_web_app(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

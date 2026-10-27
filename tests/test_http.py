import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from collector import core


@pytest.fixture
def server():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen["ua"] = self.headers.get("User-Agent")
            if self.path.startswith("/slow"):
                time.sleep(1.5)
            if self.path.startswith("/blocked"):
                body, status, ctype = b"<html>Security Violation</html>", 403, "text/html"
            else:
                body, status, ctype = b'{"success": true, "result": {}}', 200, "application/json"
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}", seen
    httpd.shutdown()


def test_sends_our_user_agent(server):
    base, seen = server
    resp = core.http_get(f"{base}/ok", 5, user_agent="flights-archive/0.1 (+https://example.org; me@example.org)")
    assert resp.status == 200 and resp.body.startswith(b'{"success"')
    assert seen["ua"] == "flights-archive/0.1 (+https://example.org; me@example.org)"


def test_error_status_comes_back_as_a_response(server):
    base, _ = server
    resp = core.http_get(f"{base}/blocked", 5, user_agent="flights-archive/0.1")
    assert resp.status == 403 and b"Security Violation" in resp.body
    with pytest.raises(core.BlockedError):
        core.parse_result(resp, "test")


def test_timeout_is_enforced(server):
    base, _ = server
    with pytest.raises(OSError):  # socket timeouts surface as TimeoutError or URLError, both OSError
        core.http_get(f"{base}/slow", 0.3, user_agent="flights-archive/0.1")


def test_blank_user_agent_is_refused():
    with pytest.raises(ValueError):
        core.http_get("http://127.0.0.1:9/", 1, user_agent="  ")

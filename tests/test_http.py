import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from collector import core

UA = "flights-archive/0.1 (+https://example.org; me@example.org)"


@pytest.fixture
def server():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen["ua"] = self.headers.get("User-Agent")
            if self.path.startswith("/slow"):
                time.sleep(1.5)
            if self.path.startswith("/redirect-same"):
                self.send_response(302)
                self.send_header("Location", "/ok")
                self.end_headers()
                return
            if self.path.startswith("/redirect-other"):
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:1/ok")  # another port is another host
                self.end_headers()
                return
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

    class QuietServer(ThreadingHTTPServer):
        def handle_error(self, request, client_address):
            pass  # the timeout test hangs up on purpose; don't print the broken pipe

    httpd = QuietServer(("127.0.0.1", 0), Handler)
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
    resp = core.http_get(f"{base}/blocked", 5, user_agent=UA)
    assert resp.status == 403 and b"Security Violation" in resp.body
    with pytest.raises(core.BlockedError):
        core.parse_result(resp, "test")


def test_timeout_is_enforced(server):
    base, _ = server
    with pytest.raises(OSError):  # socket timeouts surface as TimeoutError or URLError, both OSError
        core.http_get(f"{base}/slow", 0.3, user_agent=UA)


@pytest.mark.parametrize("ua", ["  ", "flights-archive/0.1", "flights-archive/0.1 (+https://example.org)", "me@example.org"])
def test_user_agent_without_url_and_email_is_refused(ua):
    with pytest.raises(ValueError):
        core.http_get("http://127.0.0.1:9/", 1, user_agent=ua)


def test_redirect_within_the_host_is_followed(server):
    base, _ = server
    resp = core.http_get(f"{base}/redirect-same", 5, user_agent=UA)
    assert resp.status == 200 and resp.body.startswith(b'{"success"')


def test_redirect_to_another_host_is_refused(server):
    base, _ = server
    with pytest.raises(core.CollectorError, match="redirect to http://127.0.0.1:1 refused"):
        core.http_get(f"{base}/redirect-other", 5, user_agent=UA)


def test_oversized_reply_is_refused(server, monkeypatch):
    base, _ = server
    monkeypatch.setattr(core, "MAX_BODY_BYTES", 8)
    with pytest.raises(core.CollectorError, match="larger than 8 bytes"):
        core.http_get(f"{base}/ok", 5, user_agent=UA)

#!/usr/bin/env python3
"""Deploy webhook receiver for martes.app."""
import hashlib, hmac, os, subprocess, logging
from http.server import HTTPServer, BaseHTTPRequestHandler

SECRET = os.environ.get("DEPLOY_SECRET", "")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("deploy-hook")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200); self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path != "/deploy":
            self.send_response(404); self.end_headers(); return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        if SECRET:
            sig = self.headers.get("X-Hub-Signature-256", "")
            expected = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
                log.warning("Invalid signature from %s", self.client_address[0])
                self.send_response(403); self.end_headers(); return

        log.info("Deploy triggered from %s", self.client_address[0])
        subprocess.Popen(
            ["/app/deploy.sh"],
            stdout=open("/var/log/martes-deploy.log", "a"),
            stderr=subprocess.STDOUT
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"deploying"}')


if __name__ == "__main__":
    port = int(os.environ.get("DEPLOY_PORT", 9876))
    log.info("Deploy webhook listening on 0.0.0.0:%d", port)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

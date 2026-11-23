# -*- coding = utf-8 -*-
"""假 OIDC IdP（discovery/jwks/token + RSA 签名），供 OIDC 黑盒测试。

对齐 warden server/internal/control/oidc_test.go 的 fakeOIDCProvider：
discovery 返回标准 openid-configuration，jwks 暴露 RSA 公钥，token 端点
用 RSA 私钥签 id_token。黑盒下 nonce 由 warden start 生成、测试端读取后
经 issue_code() 编码进 auth code，token 端点据此签回匹配的 nonce。
"""
from __future__ import annotations

import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class _Handler(BaseHTTPRequestHandler):
    provider = None  # 由 FakeOIDCProvider.__init__ 注入

    def do_GET(self):
        if self.path == "/.well-known/openid-configuration":
            self._json(self.provider.discovery())
        elif self.path == "/jwks":
            self._json(self.provider.jwks())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/token":
            length = int(self.headers.get("Content-Length", 0) or 0)
            form = parse_qs(self.rfile.read(length).decode("utf-8") if length else "")
            code = (form.get("code") or [""])[0]
            self._json(self.provider.token(code))
        else:
            self.send_response(404)
            self.end_headers()

    def _json(self, obj) -> None:
        data = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        pass


class FakeOIDCProvider:
    def __init__(self, host: str = "127.0.0.1", port: int = 9200, client_id: str = "warden-test-client"):
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = self.private_key.public_key()
        self.client_id = client_id
        self.issuer = f"http://{host}:{port}"
        _Handler.provider = self
        self.httpd = HTTPServer((host, port), _Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def discovery(self) -> dict:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": self.issuer + "/authorize",
            "token_endpoint": self.issuer + "/token",
            "jwks_uri": self.issuer + "/jwks",
            "end_session_endpoint": self.issuer + "/end_session",
            "id_token_signing_alg_values_supported": ["RS256"],
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
        }

    def jwks(self) -> dict:
        n = self.public_key.public_numbers().n
        e = self.public_key.public_numbers().e
        n_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big")
        e_bytes = e.to_bytes((e.bit_length() + 7) // 8, "big")
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "alg": "RS256",
                    "use": "sig",
                    "kid": "test-kid",
                    "n": _b64url(n_bytes),
                    "e": _b64url(e_bytes),
                }
            ]
        }

    def issue_code(
        self,
        nonce: str,
        sub: str = "oidc-user-1",
        email: str = "oidc-user@example.com",
        name: str = "OIDC User",
    ) -> str:
        """测试端 helper：把 nonce/身份编码进 auth code。"""
        meta = {"nonce": nonce, "sub": sub, "email": email, "name": name}
        return _b64url(json.dumps(meta).encode("utf-8"))

    def token(self, code: str) -> dict:
        try:
            padded = code + "=" * (-len(code) % 4)
            meta = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        except Exception:
            meta = {}
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "aud": self.client_id,
            "iat": now,
            "exp": now + 3600,
            "sub": meta.get("sub", "oidc-user-1"),
            "email": meta.get("email", "oidc-user@example.com"),
            "name": meta.get("name", "OIDC User"),
        }
        if meta.get("nonce"):
            claims["nonce"] = meta["nonce"]
        id_token = jwt.encode(
            claims, self.private_key, algorithm="RS256", headers={"kid": "test-kid"}
        )
        return {
            "access_token": "fake-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": id_token,
        }
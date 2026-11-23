# -*- coding = utf-8 -*-
"""联邦断言生成（与 warden server/internal/control/federated_auth.go 对齐）。

warden 只保存联邦验签公钥（WARDEN_FEDERATED_ASSERTION_PUBLIC_KEY），不保存私钥。
测试端需自持私钥，按 RS256 签发短期断言 JWT，交给 POST /api/v1/auth/federated/login。
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# 与 federated_auth.go 的过期窗口、未来时钟容忍一致
MAX_LIFETIME_SECONDS = 5 * 60


def generate_rsa_key_pair(bits: int = 2048) -> tuple[bytes, bytes]:
    """生成 RSA 密钥对，返回 (private_pem, public_pem)。

    public_pem 用于配置 warden 的 WARDEN_FEDERATED_ASSERTION_PUBLIC_KEY，
    private_pem 用于测试端签名断言。
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def build_assertion(
    private_key_pem: bytes | str,
    *,
    issuer: str,
    audience: str,
    subject: str,
    enterprise_id: str,
    workspace_id: str,
    project_id: str | None = None,
    email: str | None = None,
    display_name: str | None = None,
    workspace_role: str | None = None,
    nonce: str | None = None,
    lifetime_seconds: int = 60,
    now: int | None = None,
) -> str:
    """签发一个短期内有效的联邦断言 JWT（RS256）。

    必填/校验约束与服务端一致：sub、jti、nonce 非空；iat/exp 必填且
    exp - iat ≤ 5 分钟；enterprise_id、workspace_id 必填。
    """
    if lifetime_seconds > MAX_LIFETIME_SECONDS:
        raise ValueError(f"断言有效期不能超过 {MAX_LIFETIME_SECONDS} 秒")
    if isinstance(private_key_pem, str):
        private_key_pem = private_key_pem.encode("utf-8")

    iat = int(time.time()) if now is None else int(now)
    claims: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "jti": uuid.uuid4().hex,
        "iat": iat,
        "exp": iat + lifetime_seconds,
        "enterprise_id": enterprise_id,
        "workspace_id": workspace_id,
        "nonce": nonce or uuid.uuid4().hex,
    }
    if project_id:
        claims["project_id"] = project_id
    if email:
        claims["email"] = email
    if display_name:
        claims["name"] = display_name
    if workspace_role:
        claims["workspace_role"] = workspace_role
    return jwt.encode(claims, private_key_pem, algorithm="RS256")
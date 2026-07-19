"""Persisted OAuth transactions and single-owner sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from domain_atlas.core.db import connect


@dataclass(frozen=True)
class OAuthTransaction:
    state: str
    code_verifier: str
    code_challenge: str
    return_path: str


@dataclass(frozen=True)
class ConsumedOAuthState:
    code_verifier: str
    return_path: str


@dataclass(frozen=True)
class OwnerSession:
    github_user_id: int
    github_login: str
    csrf_token: str
    expires_at: int
    local: bool = False


@dataclass(frozen=True)
class CreatedOwnerSession:
    token: str
    session: OwnerSession


class OAuthStateRepository:
    def __init__(
        self,
        database_path: Path,
        *,
        secret: str,
        ttl_seconds: int,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.database_path = database_path
        self.secret = secret
        self.ttl_seconds = ttl_seconds
        self.now = now

    def create(self, *, return_path: str) -> OAuthTransaction:
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        challenge = _base64url(hashlib.sha256(verifier.encode("ascii")).digest())
        expires_at = int(self.now()) + self.ttl_seconds
        with connect(self.database_path) as connection:
            connection.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (int(self.now()),))
            connection.execute(
                """
                INSERT INTO oauth_states (
                    state_digest, code_verifier, return_path, expires_at
                ) VALUES (?, ?, ?, ?)
                """,
                (_digest(self.secret, "oauth-state", state), verifier, return_path, expires_at),
            )
        return OAuthTransaction(
            state=state,
            code_verifier=verifier,
            code_challenge=challenge,
            return_path=return_path,
        )

    def consume(self, state: str) -> ConsumedOAuthState | None:
        now = int(self.now())
        digest = _digest(self.secret, "oauth-state", state)
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT code_verifier, return_path
                FROM oauth_states
                WHERE state_digest = ? AND consumed_at IS NULL AND expires_at > ?
                """,
                (digest, now),
            ).fetchone()
            if row is None:
                return None
            updated = connection.execute(
                """
                UPDATE oauth_states
                SET consumed_at = ?
                WHERE state_digest = ? AND consumed_at IS NULL AND expires_at > ?
                """,
                (now, digest, now),
            )
            if updated.rowcount != 1:
                return None
        return ConsumedOAuthState(
            code_verifier=str(row["code_verifier"]),
            return_path=str(row["return_path"]),
        )


class OwnerSessionRepository:
    def __init__(
        self,
        database_path: Path,
        *,
        secret: str,
        ttl_seconds: int,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.database_path = database_path
        self.secret = secret
        self.ttl_seconds = ttl_seconds
        self.now = now

    def create(self, *, github_user_id: int, github_login: str) -> CreatedOwnerSession:
        token = secrets.token_urlsafe(48)
        now = int(self.now())
        expires_at = now + self.ttl_seconds
        with connect(self.database_path) as connection:
            connection.execute("DELETE FROM owner_sessions WHERE expires_at <= ?", (now,))
            connection.execute(
                """
                INSERT INTO owner_sessions (
                    token_digest,
                    github_user_id,
                    github_login,
                    expires_at,
                    created_at,
                    last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    _digest(self.secret, "session", token),
                    github_user_id,
                    github_login,
                    expires_at,
                    now,
                    now,
                ),
            )
        return CreatedOwnerSession(
            token=token,
            session=OwnerSession(
                github_user_id=github_user_id,
                github_login=github_login,
                csrf_token=_digest(self.secret, "csrf", token),
                expires_at=expires_at,
            ),
        )

    def resolve(self, token: str, *, expected_owner_id: int) -> OwnerSession | None:
        if not token:
            return None
        now = int(self.now())
        digest = _digest(self.secret, "session", token)
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT github_user_id, github_login, expires_at
                FROM owner_sessions
                WHERE token_digest = ?
                  AND revoked_at IS NULL
                  AND expires_at > ?
                  AND github_user_id = ?
                """,
                (digest, now, expected_owner_id),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE owner_sessions SET last_seen_at = ? WHERE token_digest = ?",
                (now, digest),
            )
        return OwnerSession(
            github_user_id=int(row["github_user_id"]),
            github_login=str(row["github_login"]),
            csrf_token=_digest(self.secret, "csrf", token),
            expires_at=int(row["expires_at"]),
        )

    def revoke(self, token: str) -> None:
        if not token:
            return
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE owner_sessions SET revoked_at = ?
                WHERE token_digest = ? AND revoked_at IS NULL
                """,
                (int(self.now()), _digest(self.secret, "session", token)),
            )

    def revoke_all(self) -> int:
        with connect(self.database_path) as connection:
            result = connection.execute(
                """
                UPDATE owner_sessions SET revoked_at = ?
                WHERE revoked_at IS NULL
                """,
                (int(self.now()),),
            )
        return result.rowcount


def local_owner_session() -> OwnerSession:
    return OwnerSession(
        github_user_id=0,
        github_login="local",
        csrf_token="",
        expires_at=2**63 - 1,
        local=True,
    )


def _digest(secret: str, purpose: str, value: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        f"{purpose}:{value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

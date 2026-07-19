"""GitHub OAuth web-flow adapter."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx


class GitHubOAuthError(RuntimeError):
    """A safe OAuth failure that does not expose provider secrets or tokens."""


@dataclass(frozen=True)
class GitHubIdentity:
    user_id: int
    login: str
    avatar_url: str = ""


class GitHubOAuthProvider(Protocol):
    def authorization_url(
        self,
        *,
        state: str,
        code_challenge: str,
        redirect_uri: str,
    ) -> str: ...

    def fetch_identity(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> GitHubIdentity: ...


class GitHubOAuthClient:
    """Minimal GitHub OAuth client that requests identity without repository scopes."""

    authorize_endpoint = "https://github.com/login/oauth/authorize"
    token_endpoint = "https://github.com/login/oauth/access_token"
    user_endpoint = "https://api.github.com/user"

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        timeout_seconds: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout_seconds = timeout_seconds
        self.client = client

    def authorization_url(
        self,
        *,
        state: str,
        code_challenge: str,
        redirect_uri: str,
    ) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "allow_signup": "false",
            }
        )
        return f"{self.authorize_endpoint}?{query}"

    def fetch_identity(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> GitHubIdentity:
        try:
            client_context = (
                nullcontext(self.client)
                if self.client is not None
                else httpx.Client(timeout=self.timeout_seconds)
            )
            with client_context as client:
                assert client is not None
                token_response = client.post(
                    self.token_endpoint,
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "code_verifier": code_verifier,
                    },
                )
                token_response.raise_for_status()
                token_payload = token_response.json()
                access_token = str(token_payload.get("access_token") or "")
                if not access_token:
                    raise GitHubOAuthError("GitHub 登录授权未成功，请重新尝试。")
                user_response = client.get(
                    self.user_endpoint,
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {access_token}",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                user_response.raise_for_status()
                user_payload = user_response.json()
        except GitHubOAuthError:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise GitHubOAuthError("GitHub 登录服务暂时不可用，请稍后重试。") from exc

        try:
            return GitHubIdentity(
                user_id=int(user_payload["id"]),
                login=str(user_payload["login"]),
                avatar_url=str(user_payload.get("avatar_url") or ""),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GitHubOAuthError("GitHub 没有返回有效的用户身份。") from exc

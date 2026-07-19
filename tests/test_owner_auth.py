from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient

from domain_atlas.auth import (
    GitHubIdentity,
    GitHubOAuthClient,
    OAuthStateRepository,
    OwnerSessionRepository,
)
from domain_atlas.core.backup import BackupScheduler
from domain_atlas.core.db import connect, initialize_database
from domain_atlas.core.settings import Settings
from domain_atlas.web.app import create_app


class FakeGitHubOAuthProvider:
    def __init__(self, *, user_id: int = 4242, login: str = "owner") -> None:
        self.identity = GitHubIdentity(user_id=user_id, login=login)
        self.authorization_calls: list[dict[str, str]] = []
        self.identity_calls: list[dict[str, str]] = []

    def authorization_url(
        self,
        *,
        state: str,
        code_challenge: str,
        redirect_uri: str,
    ) -> str:
        self.authorization_calls.append(
            {
                "state": state,
                "code_challenge": code_challenge,
                "redirect_uri": redirect_uri,
            }
        )
        return f"https://github.test/authorize?state={state}&challenge={code_challenge}"

    def fetch_identity(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> GitHubIdentity:
        self.identity_calls.append(
            {
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            }
        )
        return self.identity


def _private_settings(tmp_path, **overrides) -> Settings:
    values = {
        "data_dir": tmp_path.resolve(),
        "deployment_mode": "private_owner",
        "github_oauth_client_id": "client-id",
        "github_oauth_client_secret": "client-secret",
        "github_oauth_callback_url": "https://atlas.test/auth/callback",
        "owner_github_user_id": 4242,
        "session_secret": "s" * 48,
        "session_cookie_secure": True,
        "persistent_data_acknowledged": True,
    }
    values.update(overrides)
    return Settings(**values)


def _begin_login(client: TestClient, provider: FakeGitHubOAuthProvider, *, next_path: str = "/"):
    response = client.get(
        f"/auth/login?next={next_path}",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("https://github.test/authorize")
    return provider.authorization_calls[-1]


def _complete_login(
    client: TestClient,
    provider: FakeGitHubOAuthProvider,
    *,
    next_path: str = "/",
):
    call = _begin_login(client, provider, next_path=next_path)
    return client.get(
        "/auth/callback",
        params={"code": "temporary-code", "state": call["state"]},
        follow_redirects=False,
    )


def _csrf_from(page: str) -> str:
    match = re.search(r'name="_csrf" value="([^"]+)"', page)
    assert match is not None
    assert match.group(1)
    return match.group(1)


def test_private_mode_redirects_to_sign_in_and_hides_api_docs(tmp_path):
    provider = FakeGitHubOAuthProvider()
    client = TestClient(
        create_app(_private_settings(tmp_path), oauth_provider=provider),
        base_url="https://atlas.test",
    )

    protected = client.get("/", follow_redirects=False)

    assert protected.status_code == 303
    assert protected.headers["location"] == "/auth/sign-in?next=%2F"
    sign_in = client.get(protected.headers["location"])
    assert sign_in.status_code == 200
    assert "使用 GitHub 登录" in sign_in.text
    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_private_backup_scheduler_uses_application_lifespan(tmp_path, monkeypatch):
    events: list[str] = []
    monkeypatch.setattr(BackupScheduler, "start", lambda self: events.append("start"))
    monkeypatch.setattr(BackupScheduler, "stop", lambda self: events.append("stop"))
    app = create_app(
        _private_settings(tmp_path, backup_enabled=True),
        oauth_provider=FakeGitHubOAuthProvider(),
    )

    with TestClient(app, base_url="https://atlas.test") as client:
        assert client.get("/health").status_code == 200
        assert events == ["start"]

    assert events == ["start", "stop"]


def test_owner_oauth_login_uses_pkce_and_creates_hashed_secure_session(tmp_path):
    settings = _private_settings(tmp_path)
    provider = FakeGitHubOAuthProvider()
    client = TestClient(
        create_app(settings, oauth_provider=provider),
        base_url="https://atlas.test",
    )

    callback = _complete_login(client, provider, next_path="/domains/7")

    assert callback.status_code == 303
    assert callback.headers["location"] == "/domains/7"
    cookie = callback.headers["set-cookie"]
    assert "domain_atlas_session=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    auth_call = provider.authorization_calls[-1]
    identity_call = provider.identity_calls[-1]
    assert len(auth_call["state"]) >= 40
    assert len(auth_call["code_challenge"]) == 43
    assert identity_call["code"] == "temporary-code"
    assert identity_call["code_verifier"]
    assert identity_call["redirect_uri"] == settings.github_oauth_callback_url

    raw_token = client.cookies[settings.session_cookie_name]
    with connect(settings.database_path) as connection:
        row = connection.execute("SELECT * FROM owner_sessions").fetchone()
        state_row = connection.execute("SELECT * FROM oauth_states").fetchone()
    assert row is not None
    assert row["token_digest"] != raw_token
    assert raw_token not in repr(dict(row))
    assert state_row is not None
    assert state_row["state_digest"] != auth_call["state"]


def test_private_writes_require_session_bound_csrf_and_logout_revokes_session(tmp_path):
    settings = _private_settings(tmp_path)
    provider = FakeGitHubOAuthProvider()
    client = TestClient(
        create_app(settings, oauth_provider=provider),
        base_url="https://atlas.test",
    )
    assert _complete_login(client, provider).status_code == 303

    home = client.get("/")
    csrf = _csrf_from(home.text)
    assert "退出" in home.text
    assert client.post("/domains", data={"name": "Blocked"}).status_code == 403
    assert (
        client.post(
            "/domains",
            data={"name": "Blocked", "_csrf": "wrong"},
        ).status_code
        == 403
    )

    created = client.post(
        "/domains",
        data={"name": "Private Knowledge", "_csrf": csrf},
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert created.headers["location"] == "/domains/1"

    logged_out = client.post(
        "/auth/logout",
        data={"_csrf": csrf},
        follow_redirects=False,
    )
    assert logged_out.status_code == 303
    assert logged_out.headers["location"] == "/auth/sign-in"
    assert client.get("/", follow_redirects=False).status_code == 303


def test_all_domain_write_routes_use_central_owner_csrf_and_data_lock(tmp_path):
    app = create_app(
        _private_settings(tmp_path),
        oauth_provider=FakeGitHubOAuthProvider(),
    )

    application_routes = list(app.routes)
    for route in app.routes:
        included_router = getattr(route, "original_router", None)
        if included_router is not None:
            application_routes.extend(included_router.routes)
    write_routes = [
        route
        for route in application_routes
        if "POST" in getattr(route, "methods", set())
        and str(getattr(route, "path", "")).startswith("/domains")
    ]

    assert write_routes
    for route in write_routes:
        dependency_names = {
            dependency.call.__name__ for dependency in route.dependant.dependencies
        }
        assert {"verify_csrf", "guard_data_write"} <= dependency_names, route.path


def test_oauth_state_is_single_use_and_external_return_url_is_rejected(tmp_path):
    provider = FakeGitHubOAuthProvider()
    client = TestClient(
        create_app(_private_settings(tmp_path), oauth_provider=provider),
        base_url="https://atlas.test",
    )
    call = _begin_login(client, provider, next_path="//evil.example/steal")

    first = client.get(
        "/auth/callback",
        params={"code": "ok", "state": call["state"]},
        follow_redirects=False,
    )
    replay = client.get(
        "/auth/callback",
        params={"code": "ok", "state": call["state"]},
        follow_redirects=False,
    )

    assert first.status_code == 303
    assert first.headers["location"] == "/"
    assert replay.status_code == 400
    assert "已过期或已使用" in replay.text


def test_non_owner_github_account_is_denied_without_session(tmp_path):
    provider = FakeGitHubOAuthProvider(user_id=9999, login="someone-else")
    client = TestClient(
        create_app(_private_settings(tmp_path), oauth_provider=provider),
        base_url="https://atlas.test",
    )

    callback = _complete_login(client, provider)

    assert callback.status_code == 403
    assert "不是该私有知识库的所有者" in callback.text
    assert "domain_atlas_session" not in client.cookies
    assert client.get("/", follow_redirects=False).status_code == 303


def test_session_expiry_revocation_and_secret_rotation(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    clock = [1_000.0]
    repository = OwnerSessionRepository(
        database_path,
        secret="a" * 40,
        ttl_seconds=60,
        now=lambda: clock[0],
    )
    created = repository.create(github_user_id=4242, github_login="owner")

    assert repository.resolve(created.token, expected_owner_id=4242) is not None
    rotated = OwnerSessionRepository(
        database_path,
        secret="b" * 40,
        ttl_seconds=60,
        now=lambda: clock[0],
    )
    assert rotated.resolve(created.token, expected_owner_id=4242) is None

    repository.revoke(created.token)
    assert repository.resolve(created.token, expected_owner_id=4242) is None

    another = repository.create(github_user_id=4242, github_login="owner")
    clock[0] = 1_061.0
    assert repository.resolve(another.token, expected_owner_id=4242) is None


def test_expired_oauth_state_cannot_be_consumed(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    clock = [5_000.0]
    repository = OAuthStateRepository(
        database_path,
        secret="s" * 40,
        ttl_seconds=10,
        now=lambda: clock[0],
    )
    transaction = repository.create(return_path="/")

    clock[0] = 5_011.0

    assert repository.consume(transaction.state) is None


def test_github_oauth_client_uses_pkce_and_reads_only_current_identity():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url == "https://github.com/login/oauth/access_token":
            body = request.read().decode()
            assert "client_secret=oauth-secret" in body
            assert "code_verifier=verifier-value" in body
            return httpx.Response(200, json={"access_token": "temporary-access-token"})
        assert request.url == "https://api.github.com/user"
        assert request.headers["authorization"] == "Bearer temporary-access-token"
        return httpx.Response(
            200,
            json={"id": 4242, "login": "owner", "avatar_url": "https://avatar.test/1"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GitHubOAuthClient(
        client_id="oauth-client",
        client_secret="oauth-secret",
        client=client,
    )

    authorization_url = provider.authorization_url(
        state="state-value",
        code_challenge="challenge-value",
        redirect_uri="https://atlas.test/auth/callback",
    )
    parsed = urlparse(authorization_url)
    query = parse_qs(parsed.query)
    identity = provider.fetch_identity(
        code="temporary-code",
        code_verifier="verifier-value",
        redirect_uri="https://atlas.test/auth/callback",
    )

    assert parsed.netloc == "github.com"
    assert query["state"] == ["state-value"]
    assert query["code_challenge_method"] == ["S256"]
    assert "scope" not in query
    assert identity == GitHubIdentity(
        user_id=4242,
        login="owner",
        avatar_url="https://avatar.test/1",
    )
    assert len(requests) == 2

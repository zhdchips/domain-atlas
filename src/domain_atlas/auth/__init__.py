"""Single-owner authentication for private Domain Atlas deployments."""

from domain_atlas.auth.github import (
    GitHubIdentity,
    GitHubOAuthClient,
    GitHubOAuthError,
    GitHubOAuthProvider,
)
from domain_atlas.auth.sessions import (
    OAuthStateRepository,
    OAuthTransaction,
    OwnerSession,
    OwnerSessionRepository,
)

__all__ = [
    "GitHubIdentity",
    "GitHubOAuthClient",
    "GitHubOAuthError",
    "GitHubOAuthProvider",
    "OAuthStateRepository",
    "OAuthTransaction",
    "OwnerSession",
    "OwnerSessionRepository",
]

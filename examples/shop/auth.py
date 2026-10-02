"""Authentication for the sample shop. Illustrative application code only."""
from dataclasses import dataclass
import hashlib
import hmac


@dataclass
class User:
    id: str
    role: str


def authenticate(api_key: str, users_by_digest: dict) -> User:
    """Authenticate an API key by looking up its SHA-256 digest."""
    digest = hashlib.sha256(api_key.encode()).hexdigest()
    for saved_digest, user in users_by_digest.items():
        if hmac.compare_digest(digest, saved_digest):
            return user
    raise PermissionError("Invalid API key")


def require_admin(user: User) -> None:
    """Reject requests from users without the admin role."""
    if user.role != "admin":
        raise PermissionError("Admin role required")

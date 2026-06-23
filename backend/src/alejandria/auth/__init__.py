"""Authentication module."""

from alejandria.auth.dependencies import (
    get_current_user,
    get_optional_user,
    require_admin,
    require_role,
)
from alejandria.auth.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)

__all__ = [
    "create_access_token",
    "decode_token",
    "get_current_user",
    "get_optional_user",
    "hash_password",
    "require_admin",
    "require_role",
    "verify_password",
]

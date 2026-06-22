"""Authentication module."""

from alejandria.auth.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from alejandria.auth.dependencies import (
    get_current_user,
    get_optional_user,
    require_admin,
    require_role,
)

__all__ = [
    "create_access_token",
    "decode_token",
    "hash_password",
    "verify_password",
    "get_current_user",
    "get_optional_user",
    "require_admin",
    "require_role",
]

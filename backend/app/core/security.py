import hashlib
import secrets

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_password_hasher = PasswordHash.recommended()
# Unknown users still incur an Argon2 verification, reducing email timing leaks.
_dummy_password_hash = _password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password, password_hash)
    except UnknownHashError:
        # Corrupt/unsupported stored credentials must never authenticate.
        _password_hasher.verify(password, _dummy_password_hash)
        return False


def verify_dummy_password(password: str) -> None:
    _password_hasher.verify(password, _dummy_password_hash)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits of cryptographic randomness.


def hash_session_token(raw_token: str) -> str:
    # Fast deterministic hashing is suitable for random tokens, not passwords.
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

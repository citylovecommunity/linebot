from werkzeug.security import generate_password_hash, check_password_hash
from typing import Optional


def hash_password(plain_password: Optional[str]) -> str:
    """
    Generates a secure hash for the given password.

    Args:
        plain_password (str): The plain text password.

    Returns:
        str: The hashed password string (salt included).
    """
    # method='pbkdf2:sha256' is standard, but you can use 'scrypt' for higher security
    if plain_password is None:
        return None
    return generate_password_hash(plain_password)


def verify_password(stored_hash: str, plain_password: str) -> bool:
    """
    Verifies a plain password against the stored hash.

    Args:
        stored_hash (str): The hash stored in the database.
        plain_password (str): The password provided by the user/system.

    Returns:
        bool: True if password matches, False otherwise.
    """
    return check_password_hash(stored_hash, plain_password)

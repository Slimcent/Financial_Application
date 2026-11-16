"""Password hashing with bcrypt.

bcrypt is slow on purpose: every hash costs 2^rounds iterations, which makes guessing passwords from stolen hashes
expensive. The cost is set by the BCRYPT_ROUNDS environment variable (4 to 31, default 12, about a quarter of a
second per hash). A hash keeps the cost it was made with, so changing BCRYPT_ROUNDS does not affect verifying
existing passwords. Lower values are for tests only.

Hashing blocks the thread that runs it: async code (the services) uses the *_async functions, which run it in a
worker thread so the event loop keeps serving other requests meanwhile.
"""
import asyncio
import os

import bcrypt

BCRYPT_ROUNDS_VARIABLE = "BCRYPT_ROUNDS"
DEFAULT_BCRYPT_ROUNDS = 12
MIN_BCRYPT_ROUNDS = 4
MAX_BCRYPT_ROUNDS = 31


def bcrypt_rounds() -> int:
    """The cost of new hashes: BCRYPT_ROUNDS, or DEFAULT_BCRYPT_ROUNDS when it is not set."""
    configured = os.getenv(BCRYPT_ROUNDS_VARIABLE, "").strip()
    if not configured:
        return DEFAULT_BCRYPT_ROUNDS
    try:
        rounds = int(configured)
    except ValueError:
        raise ValueError(f"{BCRYPT_ROUNDS_VARIABLE} must be a whole number") from None
    if not MIN_BCRYPT_ROUNDS <= rounds <= MAX_BCRYPT_ROUNDS:
        raise ValueError(f"{BCRYPT_ROUNDS_VARIABLE} must be between {MIN_BCRYPT_ROUNDS} and {MAX_BCRYPT_ROUNDS}")
    return rounds


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=bcrypt_rounds())).decode()


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed_password.encode())


async def hash_password_async(password: str) -> str:
    """hash_password() in a worker thread."""
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, hashed_password: str) -> bool:
    """verify_password() in a worker thread."""
    return await asyncio.to_thread(verify_password, password, hashed_password)

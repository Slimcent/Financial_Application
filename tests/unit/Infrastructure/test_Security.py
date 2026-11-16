"""Infrastructure/Security.py: bcrypt password hashing, its configurable cost and the non-blocking variants."""
import threading

import pytest

from Infrastructure import Security
from Infrastructure.Security import (BCRYPT_ROUNDS_VARIABLE, DEFAULT_BCRYPT_ROUNDS, MAX_BCRYPT_ROUNDS,
                                     MIN_BCRYPT_ROUNDS, bcrypt_rounds, hash_password, hash_password_async,
                                     verify_password, verify_password_async)

PASSWORD = "Str0ng#Pass"


@pytest.fixture
def rounds(monkeypatch):
    """Set BCRYPT_ROUNDS (None: not set)."""

    def _rounds(value):
        if value is None:
            monkeypatch.delenv(BCRYPT_ROUNDS_VARIABLE, raising=False)
        else:
            monkeypatch.setenv(BCRYPT_ROUNDS_VARIABLE, value)

    return _rounds


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [None, "", "  "], ids=["not-set", "empty", "blank"])
def test_default_cost_is_twelve_rounds(rounds, value):
    rounds(value)

    assert bcrypt_rounds() == DEFAULT_BCRYPT_ROUNDS == 12


@pytest.mark.parametrize("value, expected", [("4", 4), (" 10 ", 10), ("31", 31)])
def test_cost_is_read_from_the_environment(rounds, value, expected):
    rounds(value)

    assert bcrypt_rounds() == expected


@pytest.mark.parametrize("value", ["twelve", "12.5", "3", "32", "-1"])
def test_invalid_cost_is_refused(rounds, value):
    rounds(value)

    with pytest.raises(ValueError, match=BCRYPT_ROUNDS_VARIABLE):
        bcrypt_rounds()


def test_bounds_are_those_of_bcrypt():
    assert (MIN_BCRYPT_ROUNDS, MAX_BCRYPT_ROUNDS) == (4, 31)


def test_hash_is_made_at_the_configured_cost(rounds):
    rounds("5")

    assert hash_password(PASSWORD).startswith("$2b$05$")


def test_default_cost_is_used_for_new_hashes(rounds, monkeypatch):
    rounds(None)
    costs = []
    real_gensalt = Security.bcrypt.gensalt
    monkeypatch.setattr(Security.bcrypt, "gensalt", lambda rounds: costs.append(rounds) or real_gensalt(4))

    hash_password(PASSWORD)

    assert costs == [12]


# ---------------------------------------------------------------------------
# Hashing and verifying
# ---------------------------------------------------------------------------

def test_hash_verifies_the_password_only(rounds):
    rounds("4")
    hashed = hash_password(PASSWORD)

    assert hashed != PASSWORD
    assert verify_password(PASSWORD, hashed)
    assert not verify_password("Wr0ng#Pass", hashed)


def test_hashes_are_salted(rounds):
    rounds("4")

    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_existing_hashes_still_verify_after_the_cost_changes(rounds):
    rounds("4")
    hashed = hash_password(PASSWORD)
    rounds("6")

    assert verify_password(PASSWORD, hashed)


@pytest.mark.asyncio
async def test_async_variants_hash_and_verify(rounds):
    rounds("4")

    hashed = await hash_password_async(PASSWORD)

    assert await verify_password_async(PASSWORD, hashed)
    assert not await verify_password_async("Wr0ng#Pass", hashed)


@pytest.mark.asyncio
@pytest.mark.parametrize("name, arguments", [("hashpw", lambda: hash_password_async(PASSWORD)),
                                             ("checkpw", lambda: verify_password_async(PASSWORD, "$2b$04$x"))],
                         ids=["hash", "verify"])
async def test_async_variants_run_bcrypt_in_a_worker_thread(rounds, monkeypatch, name, arguments):
    rounds("4")
    threads = []
    monkeypatch.setattr(Security.bcrypt, name, lambda *args: threads.append(threading.get_ident()) or b"x")

    await arguments()

    assert threads and threads[0] != threading.get_ident()

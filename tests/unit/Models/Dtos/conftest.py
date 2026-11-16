"""Helpers shared by the request and response model tests (tests/unit/Models/Dtos/Request and .../Response)."""
import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def assert_rejected():
    """Assert that building `model` from `payload` raises a ValidationError for `field`.

    `field=None` expects a model-level error (e.g. a model_validator). When `error_type` is given,
    the error reported for that location must have that pydantic error type.
    """

    def _assert_rejected(model, payload, field=None, error_type=None):
        with pytest.raises(ValidationError) as exc_info:
            model(**payload)

        expected_loc = (field,) if field else ()
        errors_at_loc = [error for error in exc_info.value.errors() if error["loc"] == expected_loc]
        assert errors_at_loc, f"expected an error at {expected_loc}, got {exc_info.value.errors()}"

        if error_type is not None:
            assert error_type in [error["type"] for error in errors_at_loc], exc_info.value.errors()

        return exc_info.value

    return _assert_rejected


@pytest.fixture
def omit():
    """Return a copy of `payload` without `field`."""

    def _omit(payload, field):
        return {key: value for key, value in payload.items() if key != field}

    return _omit

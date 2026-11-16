"""Services/Exceptions/domain_exceptions.py: the errors the services raise."""
import pytest

import Services.Exceptions as exceptions_package
from Services.Exceptions.domain_exceptions import (BusinessRuleError, ConflictError, DeleteRestrictedError,
                                                   InsufficientFundsError, InvalidInputError, NotFoundError,
                                                   PersistenceError, ServiceError)

ERRORS = [
    (NotFoundError, ServiceError),
    (ConflictError, ServiceError),
    (DeleteRestrictedError, ConflictError),
    (BusinessRuleError, ServiceError),
    (InsufficientFundsError, BusinessRuleError),
    (InvalidInputError, ServiceError),
    (PersistenceError, ServiceError),
]


@pytest.mark.parametrize("error, parent", ERRORS, ids=[error.__name__ for error, _ in ERRORS])
def test_error_hierarchy(error, parent):
    assert issubclass(error, parent)
    assert issubclass(error, ServiceError)


@pytest.mark.parametrize("error", [ServiceError, *(error for error, _ in ERRORS)],
                         ids=lambda error: error.__name__)
def test_error_carries_its_message(error):
    raised = error("Account 2600000001 does not exist.")

    assert raised.message == str(raised) == "Account 2600000001 does not exist."


def test_service_errors_are_not_value_errors():
    # Callers tell a refused operation (ServiceError) apart from an invalid request model (a ValueError).
    assert not issubclass(ServiceError, ValueError)


def test_a_failed_save_is_not_a_conflict():
    # Only a unique key clash is a conflict; a save the database refuses for another reason is a PersistenceError.
    assert not issubclass(PersistenceError, ConflictError)


def test_package_exports_every_error():
    assert set(exceptions_package.__all__) == {"ServiceError", *(error.__name__ for error, _ in ERRORS)}

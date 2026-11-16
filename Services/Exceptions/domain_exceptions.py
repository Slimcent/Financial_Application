"""Errors the services raise when a business operation cannot be carried out.

Every service error derives from ServiceError, so a caller (an Application class today, an API router later) can
handle them in one place and map each kind to a response, e.g. NotFoundError -> 404, ConflictError -> 409,
BusinessRuleError / InvalidInputError -> 400 / 422, PersistenceError -> 500.

Error messages describe what went wrong without repeating personal or account data (no email addresses, no account
numbers): they may reach API clients and logs.

When a service raises, the caller's unit of work rolls back: nothing of the failed operation is saved.
"""


class ServiceError(Exception):
    """Base class of every error raised by the services."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    """The requested record (or one the operation needs) does not exist."""


class ConflictError(ServiceError):
    """The operation conflicts with existing data, e.g. an email address or a name that is already in use."""


class DeleteRestrictedError(ConflictError):
    """The record cannot be deleted because other records depend on it (e.g. a user who has accounts or
    transactions, or an account type that accounts use)."""


class BusinessRuleError(ServiceError):
    """The operation is not allowed by a business rule, e.g. a transfer from an inactive user."""


class InsufficientFundsError(BusinessRuleError):
    """The account balance does not cover the amount of the operation."""


class InvalidInputError(ServiceError):
    """A value passed to the service is not valid (values that arrive in request models are validated there)."""


class PersistenceError(ServiceError):
    """The database refused to save the changes for a reason that is neither a conflict with other data nor a broken
    business rule (e.g. a missing required value): the operation could not be completed."""

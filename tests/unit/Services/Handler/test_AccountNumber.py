"""Services/Handler/AccountNumber.py: generating account numbers (no database: uniqueness is the service's job)."""
import pytest

from Models.Constants.AppConstants import AppConstants
from Services.Handler import AccountNumber as account_number_module
from Services.Handler.AccountNumber import ACCOUNT_NUMBER_RANDOM_DIGITS, generate_account_number


@pytest.mark.parametrize("account_type_id, type_digit", [
    (AppConstants.SavingsAccountTypeId, AppConstants.SavingsAccountNumber),
    (AppConstants.CurrentAccountTypeId, AppConstants.CurrentAccountNumber),
    (3, AppConstants.OtherAccountNumber),
    (99, AppConstants.OtherAccountNumber),
], ids=["savings", "current", "other-type", "unknown-type"])
def test_number_is_2_then_the_type_digit_then_random_digits(account_type_id, type_digit):
    number = generate_account_number(account_type_id)

    assert len(number) == 2 + ACCOUNT_NUMBER_RANDOM_DIGITS == 10
    assert number.isdigit()
    assert number[:2] == f"2{type_digit}"


def test_random_digits_come_from_the_secrets_module(monkeypatch):
    monkeypatch.setattr(account_number_module.secrets, "choice", lambda digits: "7")

    assert generate_account_number(AppConstants.SavingsAccountTypeId) == "2677777777"


def test_numbers_differ_between_calls():
    numbers = {generate_account_number(AppConstants.SavingsAccountTypeId) for _ in range(50)}

    assert len(numbers) > 45  # 10^8 possible numbers per type: repeats are practically impossible


def test_generating_is_synchronous():
    # It only generates a number: no database, no awaiting.
    assert isinstance(generate_account_number(AppConstants.CurrentAccountTypeId), str)

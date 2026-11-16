import secrets

from Models.Constants.AppConstants import AppConstants

ACCOUNT_NUMBER_RANDOM_DIGITS = 8


def generate_account_number(account_type_id: int) -> str:
    """A new 10-digit account number: "2", a digit for the account type and 8 random digits.

    Only generates the number. It is not checked against the database: the service that stores it makes sure it is
    not in use yet (and Accounts.AccountNumber is unique).
    """
    account_number = "2"

    if account_type_id == AppConstants.SavingsAccountTypeId:
        account_number += AppConstants.SavingsAccountNumber
    elif account_type_id == AppConstants.CurrentAccountTypeId:
        account_number += AppConstants.CurrentAccountNumber
    else:
        account_number += AppConstants.OtherAccountNumber

    account_number += "".join(secrets.choice("0123456789") for _ in range(ACCOUNT_NUMBER_RANDOM_DIGITS))

    return account_number

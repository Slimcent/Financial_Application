import random
import asyncio
from Infrastructure.AppConstants import AppConstants


async def generate_account_number(account_type_id: int) -> str:
    await asyncio.sleep(0.1)

    account_number = "2"

    if account_type_id == AppConstants.SavingsAccountTypeId:
        account_number += AppConstants.SavingsAccountNumber
    elif account_type_id == AppConstants.CurrentAccountTypeId:
        account_number += AppConstants.CurrentAccountNumber
    else:
        account_number += AppConstants.OtherAccountNumber

    account_number += ''.join(random.choices('0123456789', k=8))

    return account_number

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Infrastructure.Logging.logger import logger
from Models.Dtos.Request.AccountTypeRequest import AccountTypeRequest
from Models.Dtos.Response.AccountTypeResponse import AccountTypeResponse
from Models.Entities import Account, AccountType
from Services.Exceptions.domain_exceptions import ConflictError, DeleteRestrictedError, NotFoundError
from Services.Extensions.exception_handler import save_changes_async
from Services.Extensions.response_mappers import to_account_type_response
from Services.Interfaces.i_account_type_service import IAccountTypeService


class AccountTypeService(IAccountTypeService):

    async def get_all_account_types(self, unit_of_work: IUnitOfWork) -> list[AccountTypeResponse]:
        account_types = await unit_of_work.account_types.get_range_async(order_by=[AccountType.Id])

        logger.info(f"Retrieved {len(account_types)} account types.")
        return [to_account_type_response(account_type) for account_type in account_types]

    async def get_account_type_by_id(self, unit_of_work: IUnitOfWork, account_type_id: int) -> AccountTypeResponse:
        return to_account_type_response(await self._get_account_type(unit_of_work, account_type_id))

    async def add_account_type(self, unit_of_work: IUnitOfWork, request: AccountTypeRequest) -> AccountTypeResponse:
        if await unit_of_work.account_types.exists_async(AccountType.Type == request.name):
            raise ConflictError(f"Account type '{request.name}' already exists.")

        account_type = unit_of_work.account_types.add_single(AccountType(Type=request.name))
        await save_changes_async(unit_of_work, conflict=f"Account type '{request.name}' already exists.")

        logger.info(f"New account type added with Id {account_type.Id}")
        return to_account_type_response(account_type)

    async def update_account_type(self, unit_of_work: IUnitOfWork, account_type_id: int,
                                  request: AccountTypeRequest) -> AccountTypeResponse:
        account_type = await self._get_account_type(unit_of_work, account_type_id)

        if await unit_of_work.account_types.exists_async(AccountType.Type == request.name,
                                                         AccountType.Id != account_type_id):
            raise ConflictError(f"Account type '{request.name}' already exists.")

        unit_of_work.account_types.update_single(account_type, {"Type": request.name})
        await save_changes_async(unit_of_work, conflict=f"Account type '{request.name}' already exists.")

        logger.info(f"Account type with Id {account_type_id} updated.")
        return to_account_type_response(account_type)

    async def delete_account_type(self, unit_of_work: IUnitOfWork, account_type_id: int) -> None:
        account_type = await self._get_account_type(unit_of_work, account_type_id)

        if await unit_of_work.accounts.exists_async(Account.AccountTypeId == account_type_id):
            raise DeleteRestrictedError(f"Account type '{account_type.Type}' is used by accounts and cannot be "
                                        f"deleted.")

        unit_of_work.account_types.delete_single(account_type)
        await save_changes_async(unit_of_work, restricted=f"Account type '{account_type.Type}' is used by accounts and "
                                                          f"cannot be deleted.")

        logger.info(f"Account type with Id {account_type_id} deleted.")

    @staticmethod
    async def _get_account_type(unit_of_work: IUnitOfWork, account_type_id: int) -> AccountType:
        account_type = await unit_of_work.account_types.get_by_id_async(account_type_id)
        if account_type is None:
            raise NotFoundError(f"Account type with Id {account_type_id} does not exist.")
        return account_type

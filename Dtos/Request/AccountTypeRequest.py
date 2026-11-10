from Dtos.Request.base_request import AccountTypeName, BaseRequest


class AccountTypeRequest(BaseRequest):
    name: AccountTypeName

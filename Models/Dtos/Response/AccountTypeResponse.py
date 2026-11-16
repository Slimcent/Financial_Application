from Models.Dtos.Response.base_response import BaseResponse, IntegerId


class AccountTypeResponse(BaseResponse):
    account_type_id: IntegerId
    name: str

from Models.Dtos.Response.base_response import BaseResponse, IntegerId


class RoleResponse(BaseResponse):
    role_id: IntegerId
    name: str

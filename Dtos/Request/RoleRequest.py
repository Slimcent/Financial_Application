from Dtos.Request.base_request import BaseRequest, RoleName


class RoleRequest(BaseRequest):
    name: RoleName

from pydantic import Field

from Dtos.Request.base_request import BaseRequest, EmailAddress, Password, PersonName, PositiveId


class UserRequest(BaseRequest):
    last_name: PersonName
    first_name: PersonName
    email: EmailAddress
    role_id: PositiveId
    password: Password = Field(repr=False)

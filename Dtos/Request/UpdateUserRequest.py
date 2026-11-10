from Dtos.Request.base_request import BaseRequest, EmailAddress, PersonName


class UpdateUserRequest(BaseRequest):
    last_name: PersonName
    first_name: PersonName
    email: EmailAddress

from pydantic import Field

from Dtos.Request.base_request import BaseRequest, EmailAddress, Password, PersonName, Position


class StaffCreateRequest(BaseRequest):
    """Staff creation request: creates the user and the staff record."""

    last_name: PersonName
    first_name: PersonName
    email: EmailAddress
    position: Position
    password: Password = Field(repr=False)

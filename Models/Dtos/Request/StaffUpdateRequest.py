from Models.Dtos.Request.base_request import BaseRequest, EmailAddress, PersonName, Position


class StaffUpdateRequest(BaseRequest):
    """Full update of a staff member's details. Passwords are not changed by this request."""

    last_name: PersonName
    first_name: PersonName
    email: EmailAddress
    position: Position

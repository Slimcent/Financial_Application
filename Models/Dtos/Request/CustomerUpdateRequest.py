from Models.Dtos.Request.base_request import Address, BaseRequest, EmailAddress, PersonName


class CustomerUpdateRequest(BaseRequest):
    """Full update of a customer's details. Passwords and account types are not changed by this request."""

    last_name: PersonName
    first_name: PersonName
    email: EmailAddress
    address: Address

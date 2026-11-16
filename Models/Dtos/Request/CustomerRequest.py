from pydantic import Field

from Models.Dtos.Request.base_request import Address, BaseRequest, EmailAddress, Password, PersonName, PositiveId


class CustomerRequest(BaseRequest):
    """Customer creation request: creates the user, the customer record and the customer's first account."""

    last_name: PersonName
    first_name: PersonName
    email: EmailAddress
    address: Address
    account_type_id: PositiveId
    password: Password = Field(repr=False)

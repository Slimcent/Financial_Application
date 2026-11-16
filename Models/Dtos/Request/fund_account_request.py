from Models.Dtos.Request.base_request import AccountNumber, Amount, BaseRequest, Description, GuidId, PositiveId


class FundAccountRequest(BaseRequest):
    """Deposit into a customer's account: customer_id is the Customers.Id of the account owner; the transaction type
    and mode must be Deposit and Credit."""

    customer_id: GuidId
    account_number: AccountNumber
    amount: Amount
    transaction_type_id: PositiveId
    transaction_mode_id: PositiveId
    description: Description = None

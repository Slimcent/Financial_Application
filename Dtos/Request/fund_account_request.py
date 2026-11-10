from Dtos.Request.base_request import AccountNumber, Amount, BaseRequest, PositiveId


class FundAccountRequest(BaseRequest):
    customer_id: PositiveId
    account_number: AccountNumber
    amount: Amount
    transaction_type_id: PositiveId
    transaction_mode_id: PositiveId

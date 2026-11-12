from Models.Dtos.Request.base_request import AccountNumber, Amount, BaseRequest, GuidId, PositiveId


class FundAccountRequest(BaseRequest):
    customer_id: GuidId
    account_number: AccountNumber
    amount: Amount
    transaction_type_id: PositiveId
    transaction_mode_id: PositiveId

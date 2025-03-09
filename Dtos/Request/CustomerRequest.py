class CustomerRequest:
    def __init__(self, user_id: str, account_Type_Id: str, balance: float):
        self.user_id = user_id
        self.account_Type_id = account_Type_Id
        self.balance = balance

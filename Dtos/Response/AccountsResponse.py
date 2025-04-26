class AccountsResponse:
    def __init__(self, account_id: int, account_number: str, balance: float, account_type_id: int, account_type: str):
        self.account_id = account_id
        self.account_number = account_number
        self.balance = balance
        self.account_type_id = account_type_id
        self.account_type = account_type

    def __repr__(self):
        return (
            f"AccountsResponse("
            f"account_id={self.account_id}, "
            f"account_number='{self.account_number}', "
            f"balance={self.balance}, "
            f"account_type_id={self.account_type_id}, "
            f"account_type='{self.account_type}'"
            f")"
        )

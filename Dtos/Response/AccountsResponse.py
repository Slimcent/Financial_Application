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
            f"\n account_id={self.account_id},\n "
            f"account_number='{self.account_number}',\n "
            f"balance={self.balance},\n "
            f"account_type_id={self.account_type_id},\n "
            f"account_type='{self.account_type}'"
            f")"
        )

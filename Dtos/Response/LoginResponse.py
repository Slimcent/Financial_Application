import decimal


class LoginResponse:
    def __init__(self, user_id: int, last_name: str, first_name: str, email: str, role_id: int, role_name: str,
                 account_type_id: int, account_type: str, balance: decimal, position: str):
        self.user_id = user_id
        self.last_name = last_name
        self.first_name = first_name
        self.email = email
        self.role_id = role_id
        self.role_name = role_name
        self.account_type_id = account_type_id
        self.account_type = account_type
        self.balance = balance
        self.position = position

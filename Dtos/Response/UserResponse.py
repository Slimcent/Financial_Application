class UserResponse:
    def __init__(self, user_id: int, name: str, email: str, role_name: str):
        self.user_id = user_id
        self.name = name
        self.email = email
        self.role_name = role_name

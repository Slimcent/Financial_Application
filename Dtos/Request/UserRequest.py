class UserRequest:
    def __init__(self, last_name: str, first_name: str,  email: str, role_id: int, password: int):
        self.last_name = last_name
        self.first_name = first_name
        self.email = email
        self.role_id = role_id
        self.password = password

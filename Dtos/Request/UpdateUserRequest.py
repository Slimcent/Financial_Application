class UpdateUserRequest:
    def __init__(self, last_name: str, first_name: str,  email: str):
        self.last_name = last_name
        self.first_name = first_name
        self.email = email

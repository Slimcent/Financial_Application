class CustomerRequest:
    def __init__(self, last_name: str, first_name: str, email: str, address: str, account_type_id: int = None):
        self.last_name = last_name
        self.first_name = first_name
        self.email = email
        self.address = address
        self.account_type_id = account_type_id
    

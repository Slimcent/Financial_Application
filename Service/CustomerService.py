from Infrastructure.AppConstants import AppConstants


class CustomerService:
    def __init__(self, database_connection, user_service):
        self.database_connection = database_connection
        self.user_service = user_service
        self.constants = AppConstants

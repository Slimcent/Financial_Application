from Dtos.Request.UserRequest import UserRequest


class UserService:
    def __init__(self, database_connection):
        self.database_connection = database_connection

    def create_user(self, user_request: UserRequest):
        connection = self.database_connection.connect()
        if not connection:
            return None

        try:
            cursor = connection.cursor(dictionary=True)

            # Check if the user already exists
            check_query = "SELECT Id FROM Users WHERE Email = %s"
            cursor.execute(check_query, (user_request.email,))
            existing_user = cursor.fetchone()

            if existing_user:
                print("User with this email already exists")
                return None  # Return None if user exists

            insert_query = "INSERT INTO Users (Name, Email, RoleId) VALUES (%s, %s, %s)"
            cursor.execute(insert_query, (user_request.name, user_request.email, user_request.role_id))
            connection.commit()

            return cursor.lastrowid

        except Exception as e:
            print("Error creating user:", e)
            connection.rollback()
            return None

        finally:
            cursor.close()
            self.database_connection.close()

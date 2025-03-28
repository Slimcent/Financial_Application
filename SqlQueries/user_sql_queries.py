USER_QUERIES = {
    "CHECK_EXISTING_USER": "SELECT Id FROM Users WHERE Email = %s",

    "INSERT_NEW_USER": """
        INSERT INTO Users (LastName, FirstName, Email, RoleId, Password)
        VALUES (%s, %s, %s, %s, %s)
    """
}

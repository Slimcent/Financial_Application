USER_QUERIES = {
    "CHECK_EXISTING_USER": "SELECT Id FROM Users WHERE Email = %s",

    "INSERT_NEW_USER": """
        INSERT INTO Users (LastName, FirstName, Email, RoleId, Password)
        VALUES (%s, %s, %s, %s, %s)
    """,

    "GET_USER_ACTIVE_STATUS": "SELECT Id, LastName, FirstName, Active FROM Users WHERE Id = %s",

    "TOGGLE_USER_ACTIVE_STATUS": "UPDATE Users SET Active = %s WHERE Id = %s",
}

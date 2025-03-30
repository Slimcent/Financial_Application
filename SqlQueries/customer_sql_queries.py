CUSTOMER_QUERIES = {
    "CREATE_CUSTOMER": """
        INSERT INTO Customers (UserId, AccountTypeId, Balance) 
        VALUES (%s, %s, %s)
    """,

    "GET_CUSTOMER_BY_USER_ID": """
        SELECT 
            c.Id AS CustomerId, 
            c.UserId, 
            u.FirstName, 
            u.LastName, 
            u.Active, 
            r.Name,
            u.CreatedAt 
        FROM Customers c
        JOIN Users u ON u.Id = c.UserId
        LEFT JOIN Roles r ON u.RoleId = r.Id
        WHERE c.UserId = %s
    """,

    "CHECK_ACCOUNT_TYPE_EXISTS": """
        SELECT 1 FROM CustomerAccountTypes WHERE UserId = %s AND AccountTypeId = %s
    """,

    "UPDATE_ACCOUNT_TYPE": """
        UPDATE Customers 
        SET AccountTypeId = %s 
        WHERE UserId = %s
    """,

    "DELETE_CUSTOMER": """
        DELETE FROM Customer WHERE UserId = %s
    """

}

CUSTOMER_QUERIES = {
    "CREATE_CUSTOMER": """
        INSERT INTO Customers (UserId, Address) VALUES (%s, %s)
    """,

    "UPDATE_CUSTOMER": "UPDATE Customers SET Address = %s WHERE UserId = %s",

    "CREATE_ACCOUNT": """
        INSERT INTO Accounts (UserId, AccountTypeId, AccountNumber, Balance) VALUES (%s, %s, %s, %s)
    """,

    "GET_Single_CUSTOMER": """
        SELECT 
            c.Id AS CustomerId,
            c.UserId,
            c.Address,
            u.FirstName,
            u.LastName,
            u.Email,
            u.Active,
            r.Id As RoleId,
            r.Name,
            u.CreatedAt
        FROM Customers c
        JOIN Users u ON u.Id = c.UserId
        LEFT JOIN Roles r ON u.RoleId = r.Id
        WHERE c.UserId = %s
    """,

    "GET_CUSTOMER_BY_USER_ID": """
        SELECT 
            c.Id AS CustomerId,
            c.Address,
            c.UserId,
            c.Address,
            u.FirstName,
            u.LastName,
            u.Email,
            u.Active,
            r.Id AS RoleId,
            r.Name AS RoleName,
            u.CreatedAt,
            a.Id AS AccountId,
            a.AccountNumber,
            a.Balance,
            at.Id AS AccountTypeId,
            at.Type AS AccountType
        FROM Customers c
        JOIN Users u ON u.Id = c.UserId
        LEFT JOIN Roles r ON u.RoleId = r.Id
        LEFT JOIN Accounts a ON c.UserId = a.UserId
        LEFT JOIN AccountTypes at ON a.AccountTypeId = at.Id
        WHERE c.UserId = %s;
    """,

    "CHECK_ACCOUNT_TYPE_EXISTS": """
        SELECT 1 FROM Customers WHERE UserId = %s AND AccountTypeId = %s
    """,

    "UPDATE_ACCOUNT_TYPE": """
        UPDATE Customers 
        SET AccountTypeId = %s WHERE UserId = %s AND AccountTypeId = %s
    """,

    "DELETE_CUSTOMER": """
        DELETE FROM Customers WHERE UserId = %s
    """,

    "GET_CUSTOMER_ACCOUNT_TYPES": """
        SELECT AccountTypeId FROM Accounts WHERE UserId = %s
    """,

    "GET_ALL_CUSTOMERS": """
        SELECT 
            c.Id AS CustomerId,
            c.Address,
            c.UserId,
            c.Address,
            u.FirstName,
            u.LastName,
            u.Email,
            u.Active,
            r.Id AS RoleId,
            r.Name AS RoleName,
            u.CreatedAt,
            a.Id AS AccountId,
            a.AccountNumber,
            a.Balance,
            at.Id AS AccountTypeId,
            at.Type AS AccountType
        FROM Customers c
        JOIN Users u ON u.Id = c.UserId
        LEFT JOIN Roles r ON u.RoleId = r.Id
        LEFT JOIN Accounts a ON c.UserId = a.UserId
        LEFT JOIN AccountTypes at ON a.AccountTypeId = at.Id
        ORDER BY u.LastName, at.Id;
        """
}

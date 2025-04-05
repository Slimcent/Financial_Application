ACCOUNT_QUERIES = {
    "GET_CUSTOMER_ACCOUNT_DETAILS": """
        SELECT 
            u.Id AS UserId, 
            u.LastName,
            u.FirstName, 
            u.Email, 
            c.Id,
            c.AccountTypeId,
            at.Type As AccountType,
            c.AccountNumber,
            c.Balance
        FROM Customers c
        JOIN Users u ON c.UserId = u.Id
        JOIN AccountTypes at ON c.AccountTypeId = at.Id
        WHERE u.Id = %s AND c.AccountTypeId = %s
    """,

    "CREATE_ACCOUNT": """
        INSERT INTO Accounts (CustomerId, AccountTypeId, AccountNumber, Balance) 
        VALUES (%s, %s, %s, %s)
    """
}

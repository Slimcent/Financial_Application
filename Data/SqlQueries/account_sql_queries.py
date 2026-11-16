ACCOUNT_QUERIES = {
    "GET_CUSTOMER_ACCOUNT_DETAILS": """
        SELECT
            u.Id AS UserId,
            u.LastName,
            u.FirstName,
            u.Email,
            a.Id AS AccountId,
            a.AccountTypeId,
            at.Type As AccountType,
            a.AccountNumber,
            a.Balance
        FROM Accounts a
        JOIN Users u ON a.UserId = u.Id
        JOIN AccountTypes at ON a.AccountTypeId = at.Id
        WHERE u.Id = %s AND a.AccountTypeId = %s
    """,

    "CREATE_ACCOUNT": """
        INSERT INTO Accounts (Id, UserId, AccountTypeId, AccountNumber, Balance)
        VALUES (%s, %s, %s, %s, %s)
    """
}

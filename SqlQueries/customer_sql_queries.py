CUSTOMER_QUERIES = {
    "CREATE_CUSTOMER": """
        INSERT INTO Customers (UserId, AccountTypeId, Balance) 
        VALUES (%s, %s, %s)
    """
}

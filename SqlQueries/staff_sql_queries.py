STAFF_QUERIES = {
    "INSERT_NEW_STAFF": """
        INSERT INTO Staff (UserId, Position) 
        VALUES (%s, %s)
    """
}

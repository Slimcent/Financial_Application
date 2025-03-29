STAFF_QUERIES = {
    "INSERT_NEW_STAFF": """
        INSERT INTO Staff (UserId, Position) 
        VALUES (%s, %s)
    """,

    "GET_ALL_STAFF": """
        SELECT s.Id, s.Position, u.Id, u.FirstName, u.LastName, u.Active, u.CreatedAt, u.Email, u.RoleId, r.Name
        FROM Staff s
        INNER JOIN Users u ON s.UserId = u.Id
        INNER JOIN Roles r ON u.RoleId = r.Id
    """
}

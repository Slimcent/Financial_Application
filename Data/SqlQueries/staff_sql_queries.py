STAFF_QUERIES = {
    "INSERT_NEW_STAFF": """
        INSERT INTO Staff (Id, UserId, Position)
        VALUES (%s, %s, %s)
    """,

    "GET_ALL_STAFF": """
        SELECT s.Id AS StaffId, s.Position, u.Id AS UserId, u.FirstName, u.LastName, u.Active, u.CreatedAt, u.Email,
               u.RoleId, r.Name
        FROM Staff s
        INNER JOIN Users u ON s.UserId = u.Id
        INNER JOIN Roles r ON u.RoleId = r.Id
    """,

    "GET_STAFF_BY_USER_ID": """
        SELECT
            s.Id As StaffId,
            u.Id,
            u.FirstName,
            u.LastName,
            u.Email,
            s.Position,
            u.RoleId,
            r.Name,
            u.Active,
            u.CreatedAt
        FROM Staff s
        JOIN Users u ON u.Id = s.UserId
        LEFT JOIN Roles r ON u.RoleId = r.Id
        WHERE s.UserId = %s
    """,

    "UPDATE_STAFF": """
        UPDATE Staff
        SET Position = %s
        WHERE UserId = %s
    """,

    "DELETE_STAFF": """
        DELETE FROM Staff WHERE UserId = %s
    """
}

from logger import logger
from aiomysql import DictCursor
from typing import Optional, List
from Dtos.Response.AccountResponse import AccountResponse
from SqlQueries.customer_sql_queries import CUSTOMER_QUERIES


class AccountService:
    def __init__(self, database_connection):
        self.database_connection = database_connection

    async def get_all_customer_accounts(self) -> Optional[List[AccountResponse]]:
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute(CUSTOMER_QUERIES["GET_ALL_CUSTOMERS"])
                results = await cursor.fetchall()

                if not results:
                    logger.info("No customers found.")
                    return []

                customer_dict = {}

                for row in results:
                    user_id = row["UserId"]

                    if user_id not in customer_dict:
                        customer_dict[user_id] = AccountResponse(
                            user_id=user_id,
                            first_name=row["FirstName"],
                            last_name=row["LastName"],
                            email=row["Email"],
                            account_types=[]
                        )

                    customer_dict[user_id].account_types.append({
                        "account_type_id": row["AccountTypeId"],
                        "account_type_name": row["AccountType"],
                        "account_number": row["AccountNumber"],
                        "balance": str(row["Balance"] or 0)
                    })

                logger.info(f"Retrieved {len(customer_dict)} customers with accounts.")
                return list(customer_dict.values())

        except Exception as e:
            logger.error(f"Error retrieving customers: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)

import logging
from typing import Optional, Dict, List

from aiomysql import DictCursor

from SqlQueries.account_sql_queries import ACCOUNT_QUERIES
from SqlQueries.customer_sql_queries import CUSTOMER_QUERIES
from database_connection import DatabaseConnection
from logger import logger


class AccountRepository:
    def __init__(self, database_connection: DatabaseConnection):
        self.database_connection = database_connection

    async def get_all_customer_accounts(self) -> Optional[List[Dict]]:
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute(CUSTOMER_QUERIES["GET_ALL_CUSTOMERS"])
                results = await cursor.fetchall()

            return results if results else []

        except Exception as e:
            logger.error(f"Error retrieving customers: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def get_customer_account_details(self, user_id: int, account_type_id: int) -> Optional[Dict]:
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            query = ACCOUNT_QUERIES["GET_CUSTOMER_ACCOUNT_DETAILS"]
            # logging.info(f"Executing query with user_id={user_id} and account_type_id={account_type_id}")

            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute(query, (user_id, account_type_id))
                result = await cursor.fetchone()

            if not result:
                logging.info(f"No account found for UserId: {user_id}, AccountTypeId: {account_type_id}")
                return None

            logger.info("Found account details for UserId: {user_id}, AccountTypeId: {account_type_id}")
            return dict(result)

        except Exception as e:
            logging.error(f"Error retrieving account details: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)
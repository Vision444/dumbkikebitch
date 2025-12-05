import asyncpg
import asyncio
import os
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.pool = None
        self.database_url = os.getenv("DATABASE_URL")

async def initialize(self):
        """Initialize the database connection pool and create tables"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=30,
                server_settings={'application_name': 'discord_password_bot'}
            )
            
            # Create tables if they don't exist
            await self.create_tables()
            logger.info("Database connection pool initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def create_tables(self):
        """Create the passwords table if it doesn't exist"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS passwords (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            service_name TEXT NOT NULL,
            username TEXT,
            encrypted_payload BYTEA NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_user_service ON passwords(user_id, service_name);
        """

        async with self.pool.acquire() as conn:
            await conn.execute(create_table_query)

    async def add_password(
        self, user_id: int, service_name: str, username: str, encrypted_payload: bytes
    ) -> int:
        """Add a new password entry"""
        query = """
        INSERT INTO passwords (user_id, service_name, username, encrypted_payload)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """

        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                query, user_id, service_name, username, encrypted_payload
            )
            return result

    async def get_password(
        self, user_id: int, service_name: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a password entry by user_id and service_name"""
        query = """
        SELECT id, service_name, username, encrypted_payload, created_at, updated_at
        FROM passwords
        WHERE user_id = $1 AND service_name = $2
        ORDER BY created_at DESC
        LIMIT 1
        """

        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, user_id, service_name)
            return dict(result) if result else None

    async def get_all_user_services(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all services for a user"""
        query = """
        SELECT id, service_name, username, created_at, updated_at
        FROM passwords
        WHERE user_id = $1
        ORDER BY service_name, created_at
        """

        async with self.pool.acquire() as conn:
            results = await conn.fetch(query, user_id)
            return [dict(row) for row in results]

    async def get_user_service_names(self, user_id: int) -> List[str]:
        """Get all service names for a user"""
        query = """
        SELECT DISTINCT service_name
        FROM passwords
        WHERE user_id = $1
        ORDER BY service_name
        """

        async with self.pool.acquire() as conn:
            results = await conn.fetch(query, user_id)
            return [row["service_name"] for row in results]

    async def update_password(
        self,
        user_id: int,
        service_name: str,
        field: str,
        new_value: str,
        encrypted_payload: bytes = None,
    ) -> bool:
        """Update a password entry"""
        if field == "service_name":
            query = """
            UPDATE passwords 
            SET service_name = $1, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $2 AND service_name = $3
            """
            params = [new_value, user_id, service_name]
        elif field == "username":
            query = """
            UPDATE passwords 
            SET username = $1, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $2 AND service_name = $3
            """
            params = [new_value, user_id, service_name]
        elif field == "password":
            query = """
            UPDATE passwords 
            SET encrypted_payload = $1, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $2 AND service_name = $3
            """
            params = [encrypted_payload, user_id, service_name]
        else:
            return False

        async with self.pool.acquire() as conn:
            result = await conn.execute(query, *params)
            return result.endswith("1")

    async def delete_password(self, user_id: int, service_name: str) -> bool:
        """Delete a password entry"""
        query = """
        DELETE FROM passwords
        WHERE user_id = $1 AND service_name = $2
        """

        async with self.pool.acquire() as conn:
            result = await conn.execute(query, user_id, service_name)
            return result.endswith("1")

    async def search_services(
        self, user_id: int, search_term: str
    ) -> List[Dict[str, Any]]:
        """Search for services by name (partial match)"""
        query = """
        SELECT id, service_name, username, created_at, updated_at
        FROM passwords
        WHERE user_id = $1 AND service_name ILIKE $2
        ORDER BY service_name, created_at
        """

        async with self.pool.acquire() as conn:
            results = await conn.fetch(query, user_id, f"%{search_term}%")
            return [dict(row) for row in results]

    async def close(self):
        """Close the database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

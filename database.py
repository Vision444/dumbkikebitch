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
        if not self.database_url:
            # Build from individual components if DATABASE_URL not provided
            host = os.getenv("DB_HOST", "shortline.proxy.rlwy.net:58876")
            user = os.getenv("DB_USER", "postgres")
            password = os.getenv("DB_PASSWORD", "xyLqkqZvMQubrvDkBoffAzxRuMaPwCHv")
            database = os.getenv("DB_NAME", "railway")
            self.database_url = f"postgresql://{user}:{password}@{host}/{database}"

    async def initialize(self):
        """Initialize the database connection pool and create tables"""
        try:
            logger.info(
                f"Attempting to connect to database: {self.database_url.replace(self.database_url.split('@')[0].split(':')[1], '***') if '@' in self.database_url else 'URL set'}"
            )
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=30,
                server_settings={"application_name": "discord_aio_bot"},
            )

            # Create tables if they don't exist
            await self.create_tables()
            logger.info("Database connection pool initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            logger.error(f"Database URL used: {self.database_url}")
            raise

    async def create_tables(self):
        """Create all required tables for both password manager and audio downloader"""
        create_tables_query = """
        -- Passwords table
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
        
        -- Audio downloads table for tracking and metadata
        CREATE TABLE IF NOT EXISTS audio_downloads (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            artist TEXT,
            album TEXT,
            filename TEXT,
            file_size BIGINT,
            download_status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_audio_user ON audio_downloads(user_id);
        CREATE INDEX IF NOT EXISTS idx_audio_status ON audio_downloads(download_status);
        """

        async with self.pool.acquire() as conn:
            await conn.execute(create_tables_query)
            logger.info("Database tables created/verified successfully")

    # Password management methods
    async def create_password(
        self, user_id: int, service_name: str, username: str, encrypted_payload: bytes
    ) -> int:
        """Create a new password entry"""
        query = """
        INSERT INTO passwords (user_id, service_name, username, encrypted_payload)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                query, user_id, service_name, username, encrypted_payload
            )
            return result["id"]

    async def get_password(
        self, user_id: int, service_name: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a password entry"""
        query = """
        SELECT id, service_name, username, encrypted_payload, created_at, updated_at
        FROM passwords
        WHERE user_id = $1 AND service_name = $2
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, user_id, service_name)
            return dict(result) if result else None

    async def list_passwords(self, user_id: int) -> List[Dict[str, Any]]:
        """List all password services for a user"""
        query = """
        SELECT service_name, username, created_at, updated_at
        FROM passwords
        WHERE user_id = $1
        ORDER BY service_name
        """
        async with self.pool.acquire() as conn:
            results = await conn.fetch(query, user_id)
            return [dict(result) for result in results]

    async def update_password(
        self, user_id: int, service_name: str, username: str, encrypted_payload: bytes
    ) -> bool:
        """Update an existing password entry"""
        query = """
        UPDATE passwords
        SET username = $3, encrypted_payload = $4, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = $1 AND service_name = $2
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                query, user_id, service_name, username, encrypted_payload
            )
            return result == "UPDATE 1"

    async def delete_password(self, user_id: int, service_name: str) -> bool:
        """Delete a password entry"""
        query = "DELETE FROM passwords WHERE user_id = $1 AND service_name = $2"
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, user_id, service_name)
            return result == "DELETE 1"

    # Audio download tracking methods
    async def create_audio_download(
        self,
        user_id: int,
        url: str,
        title: str = None,
        artist: str = None,
        album: str = None,
    ) -> int:
        """Create a new audio download tracking entry"""
        query = """
        INSERT INTO audio_downloads (user_id, url, title, artist, album)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, user_id, url, title, artist, album)
            return result["id"]

    async def update_audio_download(
        self,
        download_id: int,
        filename: str = None,
        file_size: int = None,
        status: str = None,
        url: str = None,
        title: str = None,
        artist: str = None,
        album: str = None,
    ):
        """Update audio download status and metadata"""
        updates = []
        params = []
        param_count = 1

        if filename is not None:
            updates.append(f"filename = ${param_count}")
            params.append(filename)
            param_count += 1

        if file_size is not None:
            updates.append(f"file_size = ${param_count}")
            params.append(file_size)
            param_count += 1

        if status is not None:
            updates.append(f"download_status = ${param_count}")
            params.append(status)
            param_count += 1

        if url is not None:
            updates.append(f"url = ${param_count}")
            params.append(url)
            param_count += 1

        if title is not None:
            updates.append(f"title = ${param_count}")
            params.append(title)
            param_count += 1

        if artist is not None:
            updates.append(f"artist = ${param_count}")
            params.append(artist)
            param_count += 1

        if album is not None:
            updates.append(f"album = ${param_count}")
            params.append(album)
            param_count += 1

        if status == "completed":
            updates.append(f"completed_at = CURRENT_TIMESTAMP")

        updates.append(f"updated_at = CURRENT_TIMESTAMP")

        query = f"""
        UPDATE audio_downloads
        SET {", ".join(updates)}
        WHERE id = ${param_count}
        """
        params.append(download_id)

        async with self.pool.acquire() as conn:
            await conn.execute(query, *params)

    async def get_user_audio_downloads(
        self, user_id: int, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent audio downloads for a user"""
        query = """
        SELECT id, url, title, artist, album, filename, file_size, 
               download_status, created_at, completed_at
        FROM audio_downloads
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """
        async with self.pool.acquire() as conn:
            results = await conn.fetch(query, user_id, limit)
            return [dict(result) for result in results]

    async def close(self):
        """Close the database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

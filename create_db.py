import asyncio
import asyncpg
from urllib.parse import urlparse
import sys

async def create_db():
    try:
        # The URL in .env
        url = "postgresql+asyncpg://postgres:1234@localhost:5432/tenderiq"
        
        # Parse it to get credentials
        parsed = urlparse(url)
        user = parsed.username
        password = parsed.password
        host = parsed.hostname
        port = parsed.port
        
        # Connect to the default 'postgres' database
        print(f"Connecting to default database to create 'tenderiq'...")
        sys.stdout.flush()
        conn = await asyncpg.connect(user=user, password=password, database='postgres', host=host, port=port)
        
        # Create database
        # We need to execute CREATE DATABASE, but we can't do it inside a transaction block in postgres
        # asyncpg executes commands outside transaction blocks by default if we don't start one
        try:
            await conn.execute('CREATE DATABASE tenderiq')
            print("Successfully created database 'tenderiq'!")
        except asyncpg.exceptions.DuplicateDatabaseError:
            print("Database 'tenderiq' already exists.")
        
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(create_db())

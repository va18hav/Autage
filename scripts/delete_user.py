import sys
from pathlib import Path

# Add project root to sys.path so it works directly from CLI
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select
from services.db.database import async_session_factory
from services.db.models.user import User


async def delete_users(username: str | None = None, force: bool = False):
    async with async_session_factory() as session:
        query = select(User)
        if username:
            query = query.where(User.username == username.strip().lower())

        result = await session.execute(query)
        users = result.scalars().all()

        if not users:
            if username:
                print(f"[!] No user found with username: '{username}'")
            else:
                print("[!] No users found in the database.")
            return

        print(f"Found {len(users)} user(s):")
        for u in users:
            print(f"  - ID: {u.id} | Username: {u.username} | Name: {u.name}")

        if not force:
            prompt = "Are you sure you want to delete these user(s)? (y/N): "
            choice = input(prompt).strip().lower()
            if choice not in ("y", "yes"):
                print("[-] Aborted.")
                return

        del_stmt = delete(User)
        if username:
            del_stmt = del_stmt.where(User.username == username.strip().lower())

        await session.execute(del_stmt)
        await session.commit()
        print(f"[OK] Successfully deleted {len(users)} user(s) from the database.")

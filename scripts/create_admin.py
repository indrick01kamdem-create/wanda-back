"""
Crée un compte administrateur Wanda (User.is_admin=True + AdminAccount).

Usage :
    python -m scripts.create_admin --email admin@wanda.app --password 'motdepasse' --name "Wanda Admin" --role super_admin
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.admin import AdminAccount  # noqa: E402
from app.models.user import User  # noqa: E402


async def run(email: str, password: str, name: str, role: str) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                name=name or email.split("@")[0],
                hashed_password=hash_password(password),
                is_admin=True,
                admin_role=role,
                phone=f"admin_{email.split('@')[0][:10]}",
            )
            db.add(user)
            await db.flush()
        else:
            user.is_admin = True
            user.admin_role = role
            if password:
                user.hashed_password = hash_password(password)

        existing = (
            await db.execute(select(AdminAccount).where(AdminAccount.user_id == user.id))
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                AdminAccount(
                    user_id=user.id,
                    email=email,
                    name=user.name,
                    role=role,
                )
            )
        else:
            existing.email = email
            existing.role = role
            existing.name = user.name

        await db.commit()
        print(f"Admin '{email}' (role={role}) créé/mis à jour.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Créer un admin Wanda")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default=None)
    parser.add_argument("--role", default="super_admin",
                        choices=["super_admin", "accounting", "publicity", "forensic"])
    args = parser.parse_args()
    asyncio.run(run(args.email, args.password, args.name, args.role))


if __name__ == "__main__":
    main()

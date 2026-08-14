from app.core.database import Base
from app.models import *  # noqa: F401,F403  (enregistre tous les modèles pour Alembic)

__all__ = ["Base"]

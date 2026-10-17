from alembic import context
from sqlalchemy import create_engine, pool

from apps.api.applyos import models  # noqa: F401
from apps.api.applyos.config import settings
from apps.api.applyos.db import Base

config = context.config
url = settings().database_url
if context.is_offline_mode():
    context.configure(
        url=url, target_metadata=Base.metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

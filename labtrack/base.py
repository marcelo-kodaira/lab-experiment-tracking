"""Declarative base, naming convention, and timestamp mixins for labtrack.

The MetaData naming convention makes every constraint/index name deterministic,
so they are diffable by autogenerate and droppable by literal name in migrations.
No engine is created here, so alembic/env.py can import this module side-effect-free.
"""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    # updated_at is rewritten by the set_updated_at() DB trigger (migration 0001),
    # NOT SQLAlchemy onupdate, so bulk/raw-SQL writers stay correct.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

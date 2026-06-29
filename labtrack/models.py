"""All 15 tables for the lab experiment-tracking schema, ordered as the FK graph.

Order: lookups -> measurement catalog -> core entities -> junctions -> measurements.
CHECK constraints and composite FKs are written literally beside their columns.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Identity,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from labtrack.base import Base, CreatedAtMixin, TimestampMixin


# --- lookups (referenced via ON DELETE RESTRICT) ---
class Role(CreatedAtMixin, Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)


class ProjectStatus(CreatedAtMixin, Base):
    __tablename__ = "project_statuses"
    code: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)


class ExperimentStatus(CreatedAtMixin, Base):
    __tablename__ = "experiment_statuses"
    code: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)


class SampleType(CreatedAtMixin, Base):
    __tablename__ = "sample_types"
    code: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


# --- measurement catalog ---
class MeasurementType(TimestampMixin, Base):
    __tablename__ = "measurement_types"
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    value_kind: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(Text)  # canonical unit; numeric only
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    __table_args__ = (
        UniqueConstraint("code", name="code"),
        UniqueConstraint("id", "value_kind", name="id_value_kind"),  # composite-FK target
        CheckConstraint("value_kind IN ('numeric','categorical','text')", name="value_kind"),
        CheckConstraint("unit IS NULL OR value_kind = 'numeric'", name="unit_numeric_only"),
    )


class MeasurementTypeOption(CreatedAtMixin, Base):
    __tablename__ = "measurement_type_options"
    measurement_type_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(
        Text, primary_key=True
    )  # stored in measurements.value_category
    label: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    value_kind: Mapped[str] = mapped_column(
        Text, server_default=text("'categorical'"), nullable=False
    )  # structural constant enabling the hardening FK
    __table_args__ = (
        CheckConstraint("value_kind = 'categorical'", name="kind_is_categorical"),
        # options may only hang off a categorical-kind type
        ForeignKeyConstraint(
            ["measurement_type_id", "value_kind"],
            ["measurement_types.id", "measurement_types.value_kind"],
            ondelete="CASCADE",
            name="fk_measurement_type_options_type_id_kind",  # explicit: convention name would be 65 chars (>63 PG limit) and get silently truncated+hashed
        ),
    )

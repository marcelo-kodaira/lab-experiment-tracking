"""All 15 tables for the lab experiment-tracking schema, ordered as the FK graph.

Order: lookups -> measurement catalog -> core entities -> junctions -> measurements.
CHECK constraints and composite FKs are written literally beside their columns.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
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


# --- core entities ---
class Researcher(TimestampMixin, Base):
    __tablename__ = "researchers"
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    role_code: Mapped[str] = mapped_column(
        ForeignKey("roles.code", ondelete="RESTRICT"), nullable=False
    )
    __table_args__ = (UniqueConstraint("email", name="email"),)


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status_code: Mapped[str] = mapped_column(
        ForeignKey("project_statuses.code", ondelete="RESTRICT"), nullable=False
    )


class Experiment(TimestampMixin, Base):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status_code: Mapped[str] = mapped_column(
        ForeignKey("experiment_statuses.code", ondelete="RESTRICT"), nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="date_order",
        ),
    )


class Sample(TimestampMixin, Base):
    __tablename__ = "samples"
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)  # lab-assigned identifier
    sample_type_code: Mapped[str] = mapped_column(
        ForeignKey("sample_types.code", ondelete="RESTRICT"), nullable=False
    )
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    storage_location: Mapped[str | None] = mapped_column(Text)  # free text (hierarchy deferred)
    __table_args__ = (UniqueConstraint("code", name="code"),)


# --- junctions ---
class ProjectMember(CreatedAtMixin, Base):
    __tablename__ = "project_members"
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    researcher_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("researchers.id", ondelete="CASCADE"), primary_key=True
    )
    project_role: Mapped[str | None] = mapped_column(Text)  # 'lead' | 'collaborator'
    __table_args__ = (
        CheckConstraint(
            "project_role IS NULL OR project_role IN ('lead','collaborator')",
            name="project_role",
        ),
    )


class ExperimentParticipant(CreatedAtMixin, Base):
    __tablename__ = "experiment_participants"
    experiment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True
    )
    researcher_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("researchers.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str | None] = mapped_column(Text)  # free-form contribution role


class ExperimentSample(CreatedAtMixin, Base):
    __tablename__ = "experiment_samples"
    experiment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True
    )
    sample_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("samples.id", ondelete="RESTRICT"), primary_key=True
    )


class ExperimentLineage(CreatedAtMixin, Base):
    __tablename__ = "experiment_lineage"
    experiment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True
    )  # the follow-up
    derived_from_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True
    )  # the predecessor
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        CheckConstraint("experiment_id <> derived_from_id", name="no_self"),
        CheckConstraint(
            "relation_type IN ('replication','iteration','refinement')",
            name="relation_type",
        ),
    )

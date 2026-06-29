"""All 15 tables for the lab experiment-tracking schema, ordered as the FK graph.

Order: lookups -> measurement catalog -> core entities -> junctions -> measurements.
CHECK constraints and composite FKs are written literally beside their columns.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Numeric,
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
        UniqueConstraint("code"),  # naming convention → uq_measurement_types_code
        UniqueConstraint(
            "id", "value_kind", name="uq_measurement_types_id_value_kind"
        ),  # composite-FK target
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
    __table_args__ = (UniqueConstraint("email"),)  # naming convention → uq_researchers_email


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
        BigInteger, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
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
        Index("ix_experiments_project_id", "project_id"),
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
    __table_args__ = (UniqueConstraint("code"),)  # naming convention → uq_samples_code


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
        Index("ix_project_members_researcher_id", "researcher_id"),
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
    __table_args__ = (Index("ix_experiment_participants_researcher_id", "researcher_id"),)


class ExperimentSample(CreatedAtMixin, Base):
    __tablename__ = "experiment_samples"
    experiment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True
    )
    sample_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("samples.id", ondelete="RESTRICT"), primary_key=True
    )
    __table_args__ = (Index("ix_experiment_samples_sample_id", "sample_id"),)


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
        Index("ix_experiment_lineage_derived_from_id", "derived_from_id"),
    )


# --- measurements: value_kind polymorphism (composite FKs + biconditional CHECKs) ---
class Measurement(CreatedAtMixin, Base):
    __tablename__ = "measurements"
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    sample_id: Mapped[int | None] = mapped_column(BigInteger)  # nullable: ambient readings
    measurement_type_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    value_kind: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Discriminator (numeric|categorical|text): selects which value_* column carries the reading.",
    )
    value_numeric: Mapped[Decimal | None] = mapped_column(
        Numeric, comment="Reading when value_kind='numeric'; NULL otherwise (biconditional CHECK)."
    )
    value_text: Mapped[str | None] = mapped_column(Text)
    value_category: Mapped[str | None] = mapped_column(
        Text,
        comment="A measurement_type_options.code when value_kind='categorical'; NULL otherwise.",
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("researchers.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        # (a) value shape must match the catalog's kind. MATCH SIMPLE (PG default) means a NULL
        #     value_kind would bypass this — value_kind is NOT NULL precisely to keep it load-bearing.
        ForeignKeyConstraint(
            ["measurement_type_id", "value_kind"],
            ["measurement_types.id", "measurement_types.value_kind"],
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        # (b) categorical value must be an allowed option of this type (NULL no-ops under MATCH SIMPLE)
        ForeignKeyConstraint(
            ["measurement_type_id", "value_category"],
            ["measurement_type_options.measurement_type_id", "measurement_type_options.code"],
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        # (c) a referenced sample must belong to this experiment (NULL sample_id no-ops)
        ForeignKeyConstraint(
            ["experiment_id", "sample_id"],
            ["experiment_samples.experiment_id", "experiment_samples.sample_id"],
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        CheckConstraint("value_kind IN ('numeric','categorical','text')", name="value_kind"),
        CheckConstraint(
            "(value_kind = 'numeric') = (value_numeric IS NOT NULL)", name="numeric_biconditional"
        ),
        CheckConstraint(
            "(value_kind = 'text') = (value_text IS NOT NULL)", name="text_biconditional"
        ),
        CheckConstraint(
            "(value_kind = 'categorical') = (value_category IS NOT NULL)",
            name="categorical_biconditional",
        ),
        CheckConstraint(
            "num_nonnulls(value_numeric, value_text, value_category) = 1", name="one_value"
        ),
        Index("ix_measurements_experiment_id_measured_at", "experiment_id", "measured_at"),
        Index(
            "ix_measurements_measurement_type_id_measured_at", "measurement_type_id", "measured_at"
        ),
        Index(
            "ix_measurements_recorded_by",
            "recorded_by",
            postgresql_where=text("recorded_by IS NOT NULL"),
        ),
        Index(
            "ix_measurements_type_category",
            "measurement_type_id",
            "value_category",
            postgresql_where=text("value_category IS NOT NULL"),
        ),
        Index(
            "ix_measurements_experiment_sample",
            "experiment_id",
            "sample_id",
            postgresql_where=text("sample_id IS NOT NULL"),
        ),
        {"comment": "Single-table polymorphic readings; exactly one value_* populated per row."},
    )

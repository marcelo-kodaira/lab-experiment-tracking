"""Idempotent, FK-ordered demo seed.

Lookups are upserted (safe to re-run). Transactional entities are inserted only when
the database is empty (guard on Researcher) so `docker compose up` is re-runnable;
use `docker compose down -v` for a full reset.
"""

import os
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from labtrack import models as m


def _at(month: int, day: int) -> datetime:
    return datetime(2026, month, day, 12, 0, tzinfo=UTC)


def _upsert_lookups(s: Session) -> None:
    # Each tuple: (ORM class, rows-to-upsert).
    # pg_insert accepts ORM-mapped classes directly (avoids __table__: FromClause mypy issue).
    lookups: list[tuple[type[object], list[dict[str, object]]]] = [
        (
            m.Role,
            [
                {
                    "code": "principal_investigator",
                    "label": "Principal Investigator",
                    "sort_order": 1,
                },
                {"code": "postdoc", "label": "Postdoc", "sort_order": 2},
                {"code": "grad_student", "label": "Graduate Student", "sort_order": 3},
                {"code": "lab_technician", "label": "Lab Technician", "sort_order": 4},
            ],
        ),
        (
            m.ProjectStatus,
            [
                # NOTE: every dict in a multi-row pg_insert MUST share the same keys —
                # the column template is taken from the FIRST dict, so a missing key on row 0
                # silently drops that column for ALL rows.
                {"code": "planning", "label": "Planning", "sort_order": 1, "is_terminal": False},
                {"code": "active", "label": "Active", "sort_order": 2, "is_terminal": False},
                {"code": "completed", "label": "Completed", "sort_order": 3, "is_terminal": True},
                {"code": "cancelled", "label": "Cancelled", "sort_order": 4, "is_terminal": True},
            ],
        ),
        (
            m.ExperimentStatus,
            [
                {"code": "planned", "label": "Planned", "sort_order": 1, "is_terminal": False},
                {
                    "code": "in_progress",
                    "label": "In Progress",
                    "sort_order": 2,
                    "is_terminal": False,
                },
                {"code": "completed", "label": "Completed", "sort_order": 3, "is_terminal": True},
                {"code": "failed", "label": "Failed", "sort_order": 4, "is_terminal": True},
                {"code": "cancelled", "label": "Cancelled", "sort_order": 5, "is_terminal": True},
            ],
        ),
        (
            m.SampleType,
            [
                {"code": "soil", "label": "Soil"},
                {"code": "water", "label": "Water"},
                {"code": "blood", "label": "Blood"},
                {"code": "tissue", "label": "Tissue"},
                {"code": "chemical_compound", "label": "Chemical Compound"},
            ],
        ),
    ]
    for model, values in lookups:
        s.execute(pg_insert(model).values(values).on_conflict_do_nothing())


def _upsert_catalog(s: Session) -> None:
    types = [
        {"code": "ph", "label": "pH", "value_kind": "numeric", "unit": None},
        {
            "code": "concentration",
            "label": "Concentration",
            "value_kind": "numeric",
            "unit": "mg/L",
        },
        {"code": "temperature", "label": "Temperature", "value_kind": "numeric", "unit": "°C"},
        {
            "code": "culture_result",
            "label": "Culture Result",
            "value_kind": "categorical",
            "unit": None,
        },
        {"code": "pass_fail", "label": "Pass/Fail", "value_kind": "categorical", "unit": None},
        {"code": "observation", "label": "Observation", "value_kind": "text", "unit": None},
    ]  # uniform keys: row 0 sets the column template for the whole multi-row INSERT
    s.execute(pg_insert(m.MeasurementType).values(types).on_conflict_do_nothing())
    s.flush()
    by_code = {t.code: t for t in s.scalars(select(m.MeasurementType))}
    options = [
        {
            "measurement_type_id": by_code["culture_result"].id,
            "code": "positive",
            "label": "Positive",
        },
        {
            "measurement_type_id": by_code["culture_result"].id,
            "code": "negative",
            "label": "Negative",
        },
        {"measurement_type_id": by_code["pass_fail"].id, "code": "pass", "label": "Pass"},
        {"measurement_type_id": by_code["pass_fail"].id, "code": "fail", "label": "Fail"},
    ]
    s.execute(pg_insert(m.MeasurementTypeOption).values(options).on_conflict_do_nothing())


def seed(s: Session) -> None:
    _upsert_lookups(s)
    _upsert_catalog(s)
    s.flush()

    if s.scalar(select(m.Researcher).limit(1)) is not None:
        return  # transactional data already seeded; keep re-runs idempotent

    alice = m.Researcher(
        full_name="Dr. Alice Reyes", email="alice@lab.test", role_code="principal_investigator"
    )
    bob = m.Researcher(full_name="Bob Tran", email="bob@lab.test", role_code="postdoc")
    carol = m.Researcher(full_name="Carol Niu", email="carol@lab.test", role_code="grad_student")
    dan = m.Researcher(full_name="Dan Okoro", email="dan@lab.test", role_code="lab_technician")
    s.add_all([alice, bob, carol, dan])

    proj = m.Project(
        title="Soil Microbiome Remediation",
        status_code="active",
        description="Remediation of contaminated soil microbiomes.",
    )
    s.add(proj)
    s.flush()

    s.add_all(
        [
            m.ProjectMember(project_id=proj.id, researcher_id=alice.id, project_role="lead"),
            m.ProjectMember(project_id=proj.id, researcher_id=bob.id, project_role="collaborator"),
            m.ProjectMember(
                project_id=proj.id, researcher_id=carol.id, project_role="collaborator"
            ),
            m.ProjectMember(project_id=proj.id, researcher_id=dan.id, project_role="collaborator"),
        ]
    )

    e1 = m.Experiment(
        project_id=proj.id,
        title="Baseline soil pH survey",
        hypothesis="Contaminated plots are more acidic.",
        status_code="completed",
        start_date=_at(1, 5).date(),
        end_date=_at(1, 20).date(),
    )
    e2 = m.Experiment(
        project_id=proj.id,
        title="Remediation trial round 1",
        hypothesis="Amendment X raises pH and lowers contaminant concentration.",
        status_code="completed",
        start_date=_at(2, 1).date(),
        end_date=_at(2, 28).date(),
    )
    e3 = m.Experiment(
        project_id=proj.id,
        title="Remediation trial round 2",
        hypothesis="Round 1 result replicates with a refined dose.",
        status_code="in_progress",
        start_date=_at(3, 1).date(),
    )
    s.add_all([e1, e2, e3])
    s.flush()

    # e3 derives from BOTH e2 (replication) and e1 (iteration) -> M:N lineage
    s.add_all(
        [
            m.ExperimentLineage(
                experiment_id=e3.id, derived_from_id=e2.id, relation_type="replication"
            ),
            m.ExperimentLineage(
                experiment_id=e3.id, derived_from_id=e1.id, relation_type="iteration"
            ),
        ]
    )

    s.add_all(
        [
            m.ExperimentParticipant(experiment_id=e2.id, researcher_id=bob.id, role="lead"),
            m.ExperimentParticipant(experiment_id=e2.id, researcher_id=carol.id, role="analyst"),
            m.ExperimentParticipant(experiment_id=e3.id, researcher_id=carol.id, role="lead"),
            m.ExperimentParticipant(experiment_id=e3.id, researcher_id=dan.id, role="technician"),
        ]
    )

    s1 = m.Sample(
        code="SOIL-001",
        sample_type_code="soil",
        collected_at=_at(1, 4),
        storage_location="Freezer A / Shelf 2 / Box 7",
    )
    s2 = m.Sample(
        code="SOIL-002",
        sample_type_code="soil",
        collected_at=_at(1, 4),
        storage_location="Freezer A / Shelf 2 / Box 7",
    )
    s.add_all([s1, s2])
    s.flush()

    # SOIL-001 is reused across e1, e2, e3
    s.add_all(
        [
            m.ExperimentSample(experiment_id=e1.id, sample_id=s1.id),
            m.ExperimentSample(experiment_id=e1.id, sample_id=s2.id),
            m.ExperimentSample(experiment_id=e2.id, sample_id=s1.id),
            m.ExperimentSample(experiment_id=e3.id, sample_id=s1.id),
        ]
    )

    cat = {t.code: t for t in s.scalars(select(m.MeasurementType))}
    s.add_all(
        [
            m.Measurement(
                experiment_id=e1.id,
                sample_id=s1.id,
                measurement_type_id=cat["ph"].id,
                value_kind="numeric",
                value_numeric=Decimal("6.8"),
                measured_at=_at(1, 6),
                recorded_by=carol.id,
            ),
            m.Measurement(
                experiment_id=e2.id,
                sample_id=s1.id,
                measurement_type_id=cat["concentration"].id,
                value_kind="numeric",
                value_numeric=Decimal("12.4"),
                measured_at=_at(2, 10),
                recorded_by=bob.id,
            ),
            m.Measurement(
                experiment_id=e2.id,
                sample_id=s1.id,
                measurement_type_id=cat["culture_result"].id,
                value_kind="categorical",
                value_category="positive",
                measured_at=_at(2, 11),
                recorded_by=bob.id,
            ),
            m.Measurement(
                experiment_id=e2.id,
                sample_id=s1.id,
                measurement_type_id=cat["observation"].id,
                value_kind="text",
                value_text="Slight discoloration after 48h.",
                measured_at=_at(2, 12),
                recorded_by=carol.id,
                notes="follow up next round",
            ),
            # ambient temperature: no sample
            m.Measurement(
                experiment_id=e2.id,
                sample_id=None,
                measurement_type_id=cat["temperature"].id,
                value_kind="numeric",
                value_numeric=Decimal("22.5"),
                measured_at=_at(2, 10),
                recorded_by=dan.id,
            ),
            # authorless instrument import: no recorder
            m.Measurement(
                experiment_id=e3.id,
                sample_id=s1.id,
                measurement_type_id=cat["concentration"].id,
                value_kind="numeric",
                value_numeric=Decimal("9.8"),
                measured_at=_at(3, 5),
                recorded_by=None,
            ),
        ]
    )
    s.flush()


def main() -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as s, s.begin():
        seed(s)
    print("Seed complete.")


if __name__ == "__main__":
    main()

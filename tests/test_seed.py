from sqlalchemy import func, select
from sqlalchemy.orm import Session

from labtrack import models as m
from labtrack.seed import seed


def test_seed_creates_multi_researcher_project(session: Session) -> None:
    seed(session)
    # a project with >= 3 members
    counts = session.execute(
        select(m.ProjectMember.project_id, func.count()).group_by(m.ProjectMember.project_id)
    ).all()
    assert any(c >= 3 for _, c in counts)


def test_seed_has_multi_parent_lineage(session: Session) -> None:
    seed(session)
    rows = session.execute(
        select(m.ExperimentLineage.experiment_id, func.count()).group_by(
            m.ExperimentLineage.experiment_id
        )
    ).all()
    assert any(c >= 2 for _, c in rows)  # one experiment derived from >=2 predecessors


def test_seed_sample_used_across_experiments(session: Session) -> None:
    seed(session)
    rows = session.execute(
        select(m.ExperimentSample.sample_id, func.count()).group_by(m.ExperimentSample.sample_id)
    ).all()
    assert any(c >= 2 for _, c in rows)


def test_seed_has_all_measurement_kinds(session: Session) -> None:
    seed(session)
    kinds = set(session.scalars(select(m.Measurement.value_kind)).all())
    assert {"numeric", "categorical", "text"} <= kinds
    # at least one ambient (no sample) and one authorless (no recorder)
    assert (
        session.scalar(
            select(func.count()).select_from(m.Measurement).where(m.Measurement.sample_id.is_(None))
        )
        >= 1
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(m.Measurement)
            .where(m.Measurement.recorded_by.is_(None))
        )
        >= 1
    )


def test_seed_is_idempotent(session: Session) -> None:
    seed(session)
    seed(session)  # second call must not duplicate transactional entities
    count = session.scalar(select(func.count()).select_from(m.Researcher))
    assert count == 4

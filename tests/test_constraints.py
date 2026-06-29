from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from labtrack import models as m


def baseline(s: Session) -> dict[str, int]:
    s.add_all(
        [
            m.Role(code="pi", label="PI"),
            m.ProjectStatus(code="active", label="Active"),
            m.ExperimentStatus(code="running", label="Running"),
            m.SampleType(code="soil", label="Soil"),
        ]
    )
    s.flush()
    num = m.MeasurementType(code="ph", label="pH", value_kind="numeric")
    cat = m.MeasurementType(code="culture", label="Culture", value_kind="categorical")
    txt = m.MeasurementType(code="obs", label="Observation", value_kind="text")
    s.add_all([num, cat, txt])
    s.flush()
    s.add_all(
        [
            m.MeasurementTypeOption(measurement_type_id=cat.id, code="positive", label="Positive"),
            m.MeasurementTypeOption(measurement_type_id=cat.id, code="negative", label="Negative"),
        ]
    )
    researcher = m.Researcher(full_name="Dr A", email="a@lab.test", role_code="pi")
    project = m.Project(title="P", status_code="active")
    s.add_all([researcher, project])
    s.flush()
    exp = m.Experiment(project_id=project.id, title="E", status_code="running")
    other = m.Experiment(project_id=project.id, title="E2", status_code="running")
    sample = m.Sample(code="S1", sample_type_code="soil")
    s.add_all([exp, other, sample])
    s.flush()
    # sample linked to exp, NOT to other
    s.add(m.ExperimentSample(experiment_id=exp.id, sample_id=sample.id))
    s.flush()
    return {
        "num": num.id,
        "cat": cat.id,
        "txt": txt.id,
        "researcher": researcher.id,
        "exp": exp.id,
        "other": other.id,
        "sample": sample.id,
    }


def _now() -> datetime:
    return datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def test_numeric_measurement_accepted(session: Session) -> None:
    ids = baseline(session)
    session.add(
        m.Measurement(
            experiment_id=ids["exp"],
            sample_id=ids["sample"],
            measurement_type_id=ids["num"],
            value_kind="numeric",
            value_numeric=Decimal("6.8"),
            measured_at=_now(),
        )
    )
    session.flush()  # must not raise


def _bad(session: Session, row: m.Measurement) -> None:
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(row)
            session.flush()


def test_domain_check_rejects_unknown_kind(session: Session) -> None:
    ids = baseline(session)
    _bad(
        session,
        m.Measurement(
            experiment_id=ids["exp"],
            measurement_type_id=ids["num"],
            value_kind="boolean",
            value_numeric=Decimal("1"),
            measured_at=_now(),
        ),
    )


def test_biconditional_rejects_wrong_column(session: Session) -> None:
    ids = baseline(session)
    # numeric type but text value populated
    _bad(
        session,
        m.Measurement(
            experiment_id=ids["exp"],
            measurement_type_id=ids["num"],
            value_kind="numeric",
            value_text="x",
            measured_at=_now(),
        ),
    )


def test_one_value_rejects_two_columns(session: Session) -> None:
    ids = baseline(session)
    _bad(
        session,
        m.Measurement(
            experiment_id=ids["exp"],
            measurement_type_id=ids["txt"],
            value_kind="text",
            value_text="x",
            value_numeric=Decimal("1"),
            measured_at=_now(),
        ),
    )


def test_kind_must_match_catalog_type(session: Session) -> None:
    ids = baseline(session)
    # type is numeric but row claims categorical -> composite FK (a) to measurement_types fails
    _bad(
        session,
        m.Measurement(
            experiment_id=ids["exp"],
            measurement_type_id=ids["num"],
            value_kind="categorical",
            value_category="positive",
            measured_at=_now(),
        ),
    )


def test_categorical_value_must_be_allowed_option(session: Session) -> None:
    ids = baseline(session)
    _bad(
        session,
        m.Measurement(
            experiment_id=ids["exp"],
            measurement_type_id=ids["cat"],
            value_kind="categorical",
            value_category="maybe",
            measured_at=_now(),
        ),
    )


def test_categorical_value_allowed_option_accepted(session: Session) -> None:
    ids = baseline(session)
    session.add(
        m.Measurement(
            experiment_id=ids["exp"],
            measurement_type_id=ids["cat"],
            value_kind="categorical",
            value_category="positive",
            measured_at=_now(),
        )
    )
    session.flush()


def test_sample_must_belong_to_experiment(session: Session) -> None:
    ids = baseline(session)
    # sample is linked to exp, not to other -> composite FK (c) fails
    _bad(
        session,
        m.Measurement(
            experiment_id=ids["other"],
            sample_id=ids["sample"],
            measurement_type_id=ids["num"],
            value_kind="numeric",
            value_numeric=Decimal("1"),
            measured_at=_now(),
        ),
    )


def test_ambient_measurement_without_sample_accepted(session: Session) -> None:
    ids = baseline(session)
    session.add(
        m.Measurement(
            experiment_id=ids["exp"],
            sample_id=None,
            measurement_type_id=ids["num"],
            value_kind="numeric",
            value_numeric=Decimal("22.5"),
            measured_at=_now(),
        )
    )
    session.flush()

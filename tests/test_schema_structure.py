from labtrack import models  # noqa: F401
from labtrack.base import Base

EXPECTED_TABLES = {
    "roles",
    "project_statuses",
    "experiment_statuses",
    "sample_types",
    "measurement_types",
    "measurement_type_options",
    "researchers",
    "projects",
    "experiments",
    "samples",
    "project_members",
    "experiment_participants",
    "experiment_samples",
    "experiment_lineage",
    "measurements",
}


def test_all_tables_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_measurement_types_has_composite_unique_and_kind_check() -> None:
    t = Base.metadata.tables["measurement_types"]
    uniques = {
        tuple(sorted(c.name for c in u.columns))
        for u in t.constraints
        if u.__class__.__name__ == "UniqueConstraint"
    }
    assert ("id", "value_kind") in uniques  # composite-FK target
    assert t.c["value_kind"].nullable is False
    assert t.c["unit"].nullable is True


def test_measurement_type_options_pk() -> None:
    t = Base.metadata.tables["measurement_type_options"]
    assert [c.name for c in t.primary_key.columns] == ["measurement_type_id", "code"]


def test_experiment_project_id_not_null() -> None:
    t = Base.metadata.tables["experiments"]
    assert t.c["project_id"].nullable is False


def test_researcher_email_unique() -> None:
    t = Base.metadata.tables["researchers"]
    assert any(
        c.name == "email"
        for u in t.constraints
        for c in getattr(u, "columns", [])
        if u.__class__.__name__ == "UniqueConstraint"
    )

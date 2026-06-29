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

# Lab Experiment Tracking

A PostgreSQL data model for a research lab outgrowing spreadsheets: 15 tables, one-command bring-up, every invariant enforced by the database.

**Stack:** PostgreSQL 16 · Python 3.12 · SQLAlchemy 2.0 · Alembic · psycopg 3 · Docker

---

## 1. Quick start

```bash
cp .env.example .env          # review/adjust credentials if needed
docker compose up             # builds app image, starts db, migrates, seeds
```

What it does:

- Starts a `postgres:16` container (`db`) with a `pg_isready` healthcheck.
- Builds the `app` image from `python:3.12-slim`, installs the package, copies the migration.
- Once `db` is healthy and TCP-accepting, `app` runs `alembic upgrade head` (creates all 15 tables, the `set_updated_at()` trigger function, and per-table triggers) then `python -m labtrack.seed` (4 researchers, 6 measurements).
- `app` exits 0; `db` stays up.

Connect after seeding:

```bash
docker compose exec db psql -U labtrack -d labtrack
# or from the host if psql is installed:
psql postgresql://labtrack:labtrack@localhost:5432/labtrack
```

Full reset (wipe volume and re-run from scratch):

```bash
docker compose down -v
docker compose up
```

---

## 2. What's modeled

**15 tables:** 4 reference lookups + 1 catalog + 1 catalog-options child + 4 core entities + 4 junctions + 1 fact.

```mermaid
erDiagram
    roles                     ||--o{ researchers              : "classifies"
    project_statuses          ||--o{ projects                 : "status of"
    experiment_statuses       ||--o{ experiments              : "status of"
    sample_types              ||--o{ samples                  : "type of"

    projects                  ||--o{ experiments              : "groups"
    projects                  ||--o{ project_members          : "membership"
    researchers               ||--o{ project_members          : "membership"

    experiments               ||--o{ experiment_participants  : "team"
    researchers               ||--o{ experiment_participants  : "team"
    experiments               ||--o{ experiment_samples       : "uses"
    samples                   ||--o{ experiment_samples       : "used in"
    experiments               ||--o{ experiment_lineage       : "follows"
    experiments               ||--o{ experiment_lineage       : "precedes"

    experiments               ||--o{ measurements             : "produces"
    measurement_types         ||--o{ measurements             : "typed by"
    measurement_types         ||--o{ measurement_type_options : "allows"
    samples                   |o--o{ measurements             : "sampled from (optional)"
    measurement_type_options  |o--o{ measurements             : "allowed category (optional)"
    researchers               |o--o{ measurements             : "recorded by (optional)"

    roles {
        text code PK
        text label
    }
    project_statuses {
        text code PK
        text label
        bool is_terminal
    }
    experiment_statuses {
        text code PK
        text label
        bool is_terminal
    }
    sample_types {
        text code PK
        text label
    }
    researchers {
        bigint id PK
        text full_name
        text email UK
        text role_code FK
    }
    projects {
        bigint id PK
        text title
        text status_code FK
    }
    experiments {
        bigint id PK
        text title
        text hypothesis
        bigint project_id FK
        text status_code FK
        date start_date
        date end_date
    }
    samples {
        bigint id PK
        text code UK
        text sample_type_code FK
        timestamptz collected_at
        text storage_location
    }
    measurement_types {
        bigint id PK
        text code UK
        text value_kind
        text unit
        bool is_active
    }
    measurement_type_options {
        bigint measurement_type_id PK, FK
        text code PK
        text label
    }
    measurements {
        bigint id PK
        bigint experiment_id FK
        bigint sample_id FK "nullable"
        bigint measurement_type_id FK
        text value_kind "num/cat/text discriminator"
        numeric value_numeric "if numeric"
        text value_text "if text"
        text value_category "if categorical"
        timestamptz measured_at
        bigint recorded_by FK "nullable"
    }
    project_members {
        bigint project_id PK, FK
        bigint researcher_id PK, FK
        text project_role
    }
    experiment_participants {
        bigint experiment_id PK, FK
        bigint researcher_id PK, FK
        text role
    }
    experiment_samples {
        bigint experiment_id PK, FK
        bigint sample_id PK, FK
    }
    experiment_lineage {
        bigint experiment_id PK, FK
        bigint derived_from_id PK, FK
        text relation_type
    }
```

*Crow's-foot reading: `||` exactly one, `o{` zero-or-many, `|o` zero-or-one. The three `|o--o{` links into `measurements` are the nullable references (ambient readings with no sample, instrument imports with no recorder, numeric/text rows with no category). `experiment_lineage` is the self-referential M:N (an experiment can derive from several predecessors).*

| # | Table | Kind |
|---|-------|------|
| 1 | `roles` | lookup |
| 2 | `project_statuses` | lookup |
| 3 | `experiment_statuses` | lookup |
| 4 | `sample_types` | lookup |
| 5 | `measurement_types` | catalog |
| 6 | `measurement_type_options` | catalog child |
| 7 | `researchers` | core entity |
| 8 | `projects` | core entity |
| 9 | `experiments` | core entity |
| 10 | `samples` | core entity |
| 11 | `project_members` | junction |
| 12 | `experiment_participants` | junction |
| 13 | `experiment_samples` | junction |
| 14 | `experiment_lineage` | junction (self-referential) |
| 15 | `measurements` | fact (append-only) |

**Cardinality decisions:**

- `experiment → project`: mandatory, exactly one.
- `measurement → experiment`: mandatory; `measurement → sample`: optional (ambient readings have no sample).
- `project ⋈ researcher`, `experiment ⋈ researcher`, `experiment ⋈ sample`, `experiment ⋈ experiment` (lineage): all M:N.

---

## 3. Design principles / Non-goals

**Governing principle:** the database is the single source of truth for every invariant. There is no application layer; the schema *is* the architecture. Integrity (NOT NULL, CHECK, foreign keys, the polymorphism rules) lives in the one layer that enforces it for every writer.

**Principles adopted:**

- **YAGNI** — named rationale for every absence; a live schema change is one `Mapped[…]` + one reviewed migration.
- **DRY** — `MetaData(naming_convention)`, `TimestampMixin`, one trigger function. Stops at the Alembic boundary (migrations are a frozen ledger) and never hides literal seed data.
- **12-Factor config** — `DATABASE_URL` from env (fail-fast), `alembic.ini` url blank, `.env` gitignored, `.env.example` committed.
- **SRP at module level** — `base` / `models` / `seed` / `alembic`; O/L/I/D are not applicable (no behavioral object graph).

**Patterns explicitly rejected:**

| Pattern | Why rejected |
|---------|--------------|
| Hexagonal / Ports & Adapters | Empty hexagon; Postgres portability is an intentional anti-goal; `Engine/Dialect` already *is* the adapter |
| DDD strategic | One schema = one context; ubiquitous-language naming kept as plain schema hygiene |
| DDD tactical | No behavior to encapsulate; a Python VO re-encodes the CHECK where it isn't authoritative → drift |
| Repository pattern | `Session` already is Unit-of-Work + Identity Map |
| API / service layer | Out of scope; deliverable is a schema + run-once tooling |

**Lookup tables over native ENUMs:** `ALTER TYPE … ADD VALUE` can't be used in the same transaction it's added, values can't be dropped/reordered, and Alembic autogenerate emits nothing for enum changes. A lookup-table extend-by-INSERT (including live) + carries metadata (`label`, `sort_order`, `is_terminal`).

**`value_kind` as `TEXT + CHECK`, not ENUM or lookup table:** Adding a *kind* requires a new value column — that's a migration regardless. A lookup table would advertise runtime flexibility the 1:1-column mapping can't honor. An ENUM carries the same DDL-in-transaction problem. `TEXT + CHECK` is atomic, reversible, and honest.

---

## 4. The measurement model

`measurements` stores three incompatible value shapes in one table via *trigger-free DB-enforced polymorphism.*

**`value_kind` ∈ `{'numeric', 'categorical', 'text'}`**

| kind | column populated | column type |
|------|-----------------|-------------|
| `numeric` | `value_numeric` | `NUMERIC` (unbounded, exact decimal) |
| `categorical` | `value_category` | `TEXT` (FK-enforced against `measurement_type_options.code`) |
| `text` | `value_text` | `TEXT` (free form) |

**Three composite foreign keys enforce correctness:**

- **(a) Kind-binding FK:** `(measurement_type_id, value_kind) → measurement_types(id, value_kind)` — you cannot pick a numeric type and store a category; `value_kind NOT NULL` is load-bearing (`MATCH SIMPLE` silently skips when any referencing column is NULL, so a NULL `value_kind` would bypass the catalog binding entirely).
- **(b) Categorical-membership FK:** `(measurement_type_id, value_category) → measurement_type_options(measurement_type_id, code)` — `value_category` is NULL for numeric/text rows, so `MATCH SIMPLE` no-ops cleanly.
- **(c) Sample-belongs-to-experiment FK:** `(experiment_id, sample_id) → experiment_samples(experiment_id, sample_id)` — NULL `sample_id` no-ops (ambient readings stay legal).

**Five CHECK constraints close remaining holes:**

```sql
CONSTRAINT ck_measurements_value_kind
  CHECK (value_kind IN ('numeric','categorical','text'))          -- domain (load-bearing)
CONSTRAINT ck_measurements_numeric_biconditional
  CHECK ((value_kind = 'numeric')     = (value_numeric  IS NOT NULL))
CONSTRAINT ck_measurements_text_biconditional
  CHECK ((value_kind = 'text')        = (value_text     IS NOT NULL))
CONSTRAINT ck_measurements_categorical_biconditional
  CHECK ((value_kind = 'categorical') = (value_category IS NOT NULL))
CONSTRAINT ck_measurements_one_value
  CHECK (num_nonnulls(value_numeric, value_text, value_category) = 1)
```

The domain CHECK is load-bearing, not hygiene: the biconditionals alone are satisfied by a row with an unknown `value_kind` and all value columns NULL (every LHS false = every RHS false). `value_kind IN (…)` closes that hole; `num_nonnulls = 1` makes "exactly one populated" structural and survives adding a 4th kind later.

**Do NOT tighten the composite FKs to `MATCH FULL`** — `MATCH SIMPLE` is the deliberate design; NULL skips are intentional (optional sample, optional category).

**Adding a new measurement *type*** (e.g., `absorbance`): one `INSERT` into `measurement_types`.

**Adding a new measurement *kind*** (e.g., `image`): a migration — new value column, new biconditional CHECK branch, new composite FK variant.

**`recorded_by`:** nullable single-column FK to `researchers`, `ON DELETE SET NULL`. Authorship (who wrote this row) and participation (who is on the team) are orthogonal — instrument operators record without being participants. Nullable because instrument imports and migrated historical data are genuinely authorless. `SET NULL` policy: run `UPDATE measurements SET recorded_by = <canonical> WHERE recorded_by = <dup>` before deleting a researcher.

**Append-only:** `measurements` has `created_at` and no `updated_at` — the missing column is the deliberate signal. Corrections are new rows. The one sanctioned post-insert mutation is `recorded_by → NULL` (via `ON DELETE SET NULL`). `measured_at` is the real-world observation time (UTC), distinct from `created_at`; not constrained to the experiment window or `<= now()`.

**`value_numeric` is unbounded `NUMERIC`** (exact decimal). A single column serves heterogeneous types spanning many orders of magnitude (pH @ 2dp, absorbance @ 4dp, counts ~1e9); a fixed `NUMERIC(p,s)` would clip legitimate readings. `unit` is canonical on the measurement type (numeric only) — no per-measurement override.

---

## 5. ON DELETE matrix

Scientific records are not casually deleted; lifecycle is expressed by status, not row removal.

| FK | ON DELETE | Why |
|----|-----------|-----|
| `researchers.role_code → roles` | RESTRICT | can't delete a role in use |
| `projects.status_code → project_statuses` | RESTRICT | can't delete a status in use |
| `experiments.status_code → experiment_statuses` | RESTRICT | " |
| `samples.sample_type_code → sample_types` | RESTRICT | " |
| `experiments.project_id → projects` | RESTRICT | deleting a project with experiments must be intentional (cancel, don't delete) |
| `project_members.* → projects/researchers` | CASCADE | membership is owned by its endpoints |
| `experiment_participants.* → experiments/researchers` | CASCADE | " |
| `experiment_samples.experiment_id → experiments` | CASCADE | link owned by experiment |
| `experiment_samples.sample_id → samples` | RESTRICT | can't delete a sample still linked to experiments |
| `experiment_lineage.* → experiments` | CASCADE | a lineage edge is meaningless without both endpoints |
| `measurements.experiment_id → experiments` | CASCADE | measurements are owned by their experiment |
| `measurements.recorded_by → researchers` | SET NULL | losing a person must not destroy data |
| `measurements` composite FKs (×3) | NO ACTION | deliberate — see below |

**RESTRICT vs NO ACTION subtlety:** the composite FKs on `measurements` use `NO ACTION` (deferred to statement end), not `RESTRICT` (immediate). Deleting an experiment cascades to both `measurements` (via `experiment_id`) and `experiment_samples` (via `experiment_id`); `RESTRICT` on the `(experiment_id, sample_id)` composite FK would fire mid-cascade and abort the delete. `NO ACTION` lets the cascade complete because the referencing rows are gone by end of statement.

---

## 6. Indexing

Postgres auto-indexes primary keys and unique constraints; it does **not** auto-index the referencing side of a foreign key.

**`measurements` (fact table) — 5 indexes:**

- `ix_measurements_experiment_id_measured_at` `(experiment_id, measured_at)` — timeseries queries for a single experiment.
- `ix_measurements_measurement_type_id_measured_at` `(measurement_type_id, measured_at)` — analytics across all experiments for a given type.
- `ix_measurements_recorded_by` `(recorded_by) WHERE recorded_by IS NOT NULL` — partial index; sparse FK (many rows are authorless instrument imports).
- `ix_measurements_type_category` `(measurement_type_id, value_category) WHERE value_category IS NOT NULL` — partial index; only categorical rows have a non-null category.
- `ix_measurements_experiment_sample` `(experiment_id, sample_id) WHERE sample_id IS NOT NULL` — partial index; supports the composite FK lookup for non-ambient readings only.

**Junction / FK reverse-lookup — 5 indexes:**

- `ix_experiments_project_id` — reverse-lookup experiments by project.
- `ix_project_members_researcher_id` — reverse-lookup project memberships by researcher.
- `ix_experiment_participants_researcher_id` — reverse-lookup experiment participants by researcher.
- `ix_experiment_samples_sample_id` — reverse-lookup experiment assignments by sample.
- `ix_experiment_lineage_derived_from_id` — reverse-lookup lineage edges by predecessor experiment.

---

## 7. Assumptions

1. **Per-project role** (`project_members.project_role`: lead/collaborator) added beyond the brief's lab-wide role.
2. **Experiment team is M:N** (`experiment_participants`) rather than a single lead; participant role is free-form.
3. **Lineage is M:N** with typed `relation_type`; only self-loops are DB-prevented. Deeper cycle prevention is app-level.
4. **`recorded_by`** captures the writeup author; nullable; `SET NULL` on researcher delete (see §4 runbook).
5. **`value_kind` ∈ {numeric, categorical, text}.** A genuinely new *kind* needs a migration; a new measurement *type* needs only an `INSERT`.
6. **Unit** is canonical on the measurement type (numeric only); no per-measurement override.
7. **`value_numeric` is unbounded `NUMERIC`** (exact decimal); per-type precision is not DB-enforced.
8. **Categorical allowed values** live in `measurement_type_options` and are FK-enforced; option-level soft-deactivation is app-level.
9. **`measured_at`** is real-world observation time (UTC), not constrained to the experiment window or `<= now()`.
10. **Measurements are append-only** (no `updated_at`); corrections are new rows.
11. **No soft-delete.** Lifecycle via status (projects/experiments) and `is_active` (catalog).
12. **`storage_location`** is free text; structured location hierarchy is deferred.
13. **`samples.code`, `researchers.email`, `measurement_types.code`** are natural unique business keys atop surrogate bigint PKs.
14. **Ambient measurements** (`sample_id NULL`) are allowed; sample-belongs-to-experiment is enforced structurally for non-null samples.
15. **Target platform:** PostgreSQL 16, Python 3.12, SQLAlchemy 2.0, Alembic, psycopg 3.

---

## 8. Tradeoffs & what we chose not to do

- **Trigger-free polymorphism (composite FKs + biconditional CHECKs)** over JSONB / EAV / class-table inheritance. Buys DB-enforced type safety and queryable columns; costs a DDL change to add a *kind*. JSONB was rejected (no type safety, illegal categories accepted); per-type tables were rejected (DDL per kind, join sprawl).

- **`TEXT + CHECK` for `value_kind`** over native ENUM or lookup table. Buys atomic, reversible migrations and honesty about DDL-variability. An ENUM can't add-and-use a value in one transaction; autogenerate is blind to it. A lookup table would advertise runtime flexibility the 1:1-column mapping can't honor.

- **Lookup tables** for statuses/types over enums/CHECK. Buys extend-by-INSERT (including live) and metadata (`label`, `sort_order`, `is_terminal`); costs small tables + a join for the human label.

- **M:N lineage & team** (richer than the brief's singular phrasing) over self-FK/single-lead. Buys live headroom; costs more joins and app-level cycle prevention.

- **DB-as-source-of-truth with no app/repository/hexagonal layer.** Proportionate to a schema deliverable; costs portability — an intentional non-goal.

- **Chose NOT to do — a full audit/history layer.** No status-transition history, no temporal/row-versioned measurements, no attribution audit table. Significant complexity with no stated requirement; append-only + `created_at` + `is_active` cover v1. **This is the first thing that would be added if asked.** Also deferred: units/dimensions table, censored-reading `value_operator`, `measurements` partitioning, UUID PKs, per-measurement unit override, option-level soft-deactivation.

---

## 9. Open questions for the lab

1. Do you record **below-detection-limit / censored** results (`<0.01`, `ND`, ranges)? → drives a `value_operator`.
2. Do you need **unit standardization / dimensional consistency** (a units table), or is canonical-unit-per-type enough?
3. Are **researchers ever hard-deleted** while owning recorded data? If so, preserve attribution (snapshot/audit) or null it?
4. Do you need **status-change history** (who/when) and enforcement of **illegal transitions**?
5. Can a measurement be **dated before its experiment's start** (pre-registration/backfill)? Warn, block, or allow?
6. Expected **measurement volume** — thousands, or high-frequency instrument streams (millions)? → drives partitioning.
7. Should follow-up experiments **cross projects**, and do you need **cycle detection** on lineage?
8. **Sample lifecycle:** do you track quantity/consumption, depletion, aliquots / parent-child splits, chain of custody?
9. **Storage location:** free text, or a structured freezer→shelf→box→position hierarchy?
10. Should **categorical option deprecation** hard-block new writes (needs trigger/app rule)?
11. **Multiple recorders** per measurement (co-authorship)?
12. Do **projects** need start / end / target dates?

---

## 10. Verification commands

**Bring up the database (if not already running):**

```bash
docker compose up -d db
```

**Code quality:**

```bash
ruff format .
ruff check .
mypy labtrack
```

All three must exit 0 cleanly. Alembic migrations in `alembic/versions/` are excluded from ruff by `extend-exclude`.

**Run tests** (requires DB up):

```bash
DATABASE_URL=postgresql+psycopg://labtrack:labtrack@localhost:5432/labtrack pytest
```

**Check for schema drift** (requires a fresh DB with `upgrade head` applied):

```bash
DATABASE_URL=postgresql+psycopg://labtrack:labtrack@localhost:5432/labtrack alembic check
```

Expected output: `No new upgrade operations detected.` Note: autogenerate does not detect trigger functions, trigger definitions, or CHECK body changes — see §11.

**Smoke-test CHECKs fire** (optional, from psql):

```sql
-- This must be rejected: value_kind='numeric' but value_category populated, not value_numeric
INSERT INTO measurements (experiment_id, measurement_type_id, value_kind, value_category, measured_at)
VALUES (1, 1, 'numeric', 'positive', now());
-- ERROR: new row for relation "measurements" violates check constraint "ck_measurements_numeric_biconditional"
```

**Verify seed row counts:**

```bash
docker compose exec -T db psql -U labtrack -d labtrack -c "SELECT count(*) FROM measurements;"
# expect 6
docker compose exec -T db psql -U labtrack -d labtrack -c "SELECT count(*) FROM researchers;"
# expect 4
```

---

## 11. Autogenerate caveats

Alembic `autogenerate` detects most schema changes but has deliberate blind spots — every generated revision is hand-reviewed before commit.

**What autogenerate does NOT emit:**

- **PL/pgSQL functions and triggers** — neither `CREATE FUNCTION set_updated_at()` nor any `CREATE TRIGGER` is detected or diffed. Every new table that needs the `updated_at` trigger must have its `CREATE TRIGGER` hand-added to the migration.
- **CHECK constraint bodies** — autogenerate compares CHECK existence by name, not body text. A renamed or modified `ck_measurements_*` won't surface as a diff on an existing table.
- **Composite-FK `MATCH` semantics** — `MATCH SIMPLE` vs `MATCH FULL` is not diffed on existing foreign keys. Do NOT change `MATCH` mode without a hand-written `op.drop_constraint` / `op.create_foreign_key` pair.
- **Server defaults** — `compare_server_default` is left `False` (the Alembic default) to avoid false positives from `func.now()` vs `text('now()')` representation differences.

**What autogenerate does detect:**

- Column additions, removals, type changes (`compare_type=True` is set explicitly).
- Table creations and drops.
- Index additions and drops (indexes declared in `__table_args__`).
- Column-level `comment=` changes (comments on `measurements` columns round-trip cleanly).

**The "add a `value_kind`" flow** needs a hand-written migration to: add the new value column, add the new biconditional `CHECK` branch, update `ck_measurements_one_value`, and add the new composite FK variant. Autogenerate will detect the column addition but not the CHECK changes.

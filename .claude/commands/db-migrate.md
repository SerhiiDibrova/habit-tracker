You need to create and apply an Alembic migration after SQLAlchemy model changes.

Work from the `backend/` directory with the virtualenv active.

## 1. Confirm models are imported in the migration env

Check that `backend/alembic/env.py` imports all SQLAlchemy models so autogenerate can detect them. If any model is missing from the imports, add it before proceeding.

## 2. Generate the migration

```bash
cd backend && source .venv/bin/activate && alembic revision --autogenerate -m "<describe the change>"
```

Use a short, lowercase, underscore-separated description matching what changed — for example: `add_check_ins_table` or `add_status_index_to_habits`.

## 3. Inspect the generated file

Read the new file in `backend/alembic/versions/`. Verify:

- `upgrade()` contains the expected `CREATE TABLE`, `ADD COLUMN`, or `CREATE INDEX` operations
- `downgrade()` correctly reverses the upgrade
- No unexpected drops or alterations are present
- UUIDs use `postgresql.UUID` or equivalent, not plain strings

If anything looks wrong, edit the migration file before applying.

## 4. Apply the migration

```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

## 5. Confirm

```bash
cd backend && source .venv/bin/activate && alembic current
```

Report the revision hash and confirm it matches the file just created. If the upgrade failed, show the full error and stop.

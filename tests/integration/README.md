# Integration tests

`test_import_pipeline.py` runs when `TEST_DATABASE_URL` points to a migrated PostgreSQL database. It verifies API upload, SHA/file/sheet/row lineage, PostgreSQL worker claiming, `awaiting_mapping`, blank-versus-zero preservation, and the append-only trigger. CI provisions PostgreSQL 17 and applies Alembic before pytest.

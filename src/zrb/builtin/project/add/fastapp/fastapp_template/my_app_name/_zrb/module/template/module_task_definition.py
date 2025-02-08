# 🔐 Run/Migrate My Module ==========================================================

run_my_module = app_run_group.add_task(
    run_microservice("my_module", 3000), alias="svc-my-module"
)
prepare_venv >> run_my_module >> run_microservices

create_my_module_migration = app_create_migration_group.add_task(
    create_migration("my_module"), alias="my_module"
)
prepare_venv >> create_my_module_migration >> create_all_migration

migrate_monolith_my_module = migrate_module("my_module", as_microservices=False)
prepare_venv >> migrate_monolith_my_module >> [migrate_monolith, run_monolith]

migrate_microservices_my_module = app_migrate_group.add_task(
    migrate_module("my_module", as_microservices=True),
    alias="svc-my-module",
)

(
    prepare_venv
    >> migrate_microservices_my_module
    >> [migrate_microservices, run_my_module]
)

migrate_test_my_module = migrate_module(
    "my_module", as_microservices=False, additional_env_vars=TEST_ENV_VARS
)
prepare_venv >> migrate_test_my_module >> migrate_test

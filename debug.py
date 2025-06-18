import os
import json
import toml
import dlt
from dlt.sources.sql_database import sql_database

# 🧭 Load TOML config
CONFIG_PATH = "C:/Properly_DWH_DLT/.dlt/config.toml"
os.environ["DLT_CONFIG_FILES"] = CONFIG_PATH
config = toml.load(CONFIG_PATH)

def source(section_name: str):
    params = config["sources"][section_name]
    base = sql_database.clone(name="sql_database", section=section_name)
    return base(
        schema=params["schema"],
        table_names=params["tables"],
        backend=params.get("backend", "pyarrow")
    )

def run():
    section = "erp_solvio"
    pipeline = dlt.pipeline(
        pipeline_name="sql_to_sql_erp_solvio",
        destination="mssql",
        dataset_name="test",
        dev_mode=True,
    )

    src = source(section)
    src.add_limit(1)

    # 🛠 Apply non-column hints in code
    for resource in src.resources.values():
        resource.apply_hints(
            incremental=dlt.sources.incremental("WijzigingsDatum", on_cursor_value_missing="include"),
            write_disposition="merge",
            primary_key="ID"
        )

    # 🎯 Trigger schema inference (should pick up TOML column hint)
    pipeline.extract(src)

    schema_dict = pipeline.default_schema.to_dict()
    table = "aan_aankoopfactuur"
    column = "nu_te_betalen_bedrag"

    print("📋 Inferred tables:", list(schema_dict["tables"].keys()))
    print(f"🔍 Inferred schema for {column}:")
    print(json.dumps(schema_dict["tables"][table]["columns"][column], indent=2))

    # 🧭 Verify TOML hint is parsed and present
    toml_hint = dlt.config.get(f"tool.dlt.hints.sql_to_sql_erp_solvio.{table}")
    print(f"📦 TOML hint for {column}:")
    print(json.dumps(toml_hint.get("columns_meta", {}).get(column), indent=2))

    # 💾 Export inferred schema
    schema_path = "C:/Properly_DWH_DLT/schema_preview.json"
    with open(schema_path, "w") as f:
        json.dump(schema_dict, f, indent=2)
    print(f"📄 Schema saved to: {schema_path}")

    # 🚚 Attempt to load data using inferred schema
    info = pipeline.run(src)
    print(info)

if __name__ == "__main__":
    run()

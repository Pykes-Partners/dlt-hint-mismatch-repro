import os
import json
import toml
import difflib

# 🧭 Load TOML config
CONFIG_PATH = "C:/Properly_DWH_DLT/.dlt/config.toml"
os.environ["DLT_CONFIG_FILES"] = CONFIG_PATH
config = toml.load(CONFIG_PATH)

import dlt
from dlt.sources.sql_database import sql_database


def compare_hints_to_schema(schema_dict, toml_config_path, section_name, table_name):
    print(f"\n🔍 Running config/schema check for table: {table_name}")

    # Load TOML config and pull the specific hint section
    config = toml.load(toml_config_path)
    hint_path = f"tool.dlt.hints.sql_to_sql_{section_name}.{table_name}.columns_meta"
    try:
        hints = config["tool"]["dlt"]["hints"][f"sql_to_sql_{section_name}"][table_name]["columns_meta"]
    except KeyError:
        print(f"⚠️ No config hints found for {hint_path}")
        return

    # Pull columns from schema
    try:
        schema_cols = schema_dict["tables"][table_name]["columns"]
    except KeyError:
        print(f"❌ Table '{table_name}' not found in schema.")
        return

    for col_hint in hints:
        match = schema_cols.get(col_hint)
        if match:
            print(f"✅ Hint matches schema column: {col_hint}")
        else:
            closest = difflib.get_close_matches(col_hint, schema_cols.keys(), n=1)
            suggestion = f"(Did you mean: {closest[0]})" if closest else ""
            print(f"❌ Hint column '{col_hint}' not in schema {suggestion}")
    
    # Optional: highlight precision mismatches
    for col in hints:
        if col in schema_cols and "precision" in hints[col]:
            hint_precision = hints[col]["precision"]
            actual_precision = schema_cols[col].get("precision")
            if actual_precision != hint_precision:
                print(f"⚠️ Mismatch: Column '{col}' precision hint = {hint_precision}, but schema = {actual_precision}")

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

    compare_hints_to_schema(
        schema_dict=pipeline.default_schema.to_dict(),
        toml_config_path="C:/Properly_DWH_DLT/.dlt/config.toml",
        section_name="erp_solvio",
        table_name="aan_aankoopfactuur"
    )

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

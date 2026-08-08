from django.db import migrations, connection


def add_column_if_missing(apps, schema_editor):
    """
    Defensive fix: production migration history apparently already
    marked 0008_farm_distributor_name as applied, but the actual
    column was never created (or was lost) - so plain migrate
    silently no-ops. This checks the real database schema directly
    and adds the column only if it is actually missing.
    """
    table_name = "crm_core_farm"
    column_name = "distributor_name"

    with connection.cursor() as cursor:
        existing_columns = [
            col.name for col in connection.introspection.get_table_description(cursor, table_name)
        ]

    if column_name not in existing_columns:
        with connection.schema_editor() as schema_editor_ctx:
            from django.db import models
            field = models.CharField(
                max_length=255, blank=True, default="",
                help_text="Distributor associated with this farm account."
            )
            field.set_attributes_from_name(column_name)
            schema_editor_ctx.add_field(
                apps.get_model("crm_core", "Farm"),
                field,
            )
            print(f"Added missing column {column_name} to {table_name}")
    else:
        print(f"Column {column_name} already exists on {table_name}, skipping")


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("crm_core", "0008_farm_distributor_name"),
    ]

    operations = [
        migrations.RunPython(add_column_if_missing, reverse_noop),
    ]
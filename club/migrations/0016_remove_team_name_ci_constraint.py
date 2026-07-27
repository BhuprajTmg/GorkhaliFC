from django.db import migrations


def drop_ci_constraint_if_present(apps, schema_editor):
    """Drop the expression unique index if an older 0015 created it.

    Some PythonAnywhere / SQLite setups error on Lower() unique indexes and
    can leave the site returning HTTP 500 until this is removed.
    """
    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute(
                'DROP INDEX IF EXISTS "uniq_teamregistration_team_name_ci"'
            )
        except Exception:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ("club", "0015_unique_team_name"),
    ]

    operations = [
        migrations.RunPython(drop_ci_constraint_if_present, migrations.RunPython.noop),
    ]

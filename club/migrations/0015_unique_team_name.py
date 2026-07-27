from django.db import migrations, models
import django.db.models.functions


def dedupe_team_names(apps, schema_editor):
    """Keep the earliest registration per team name (case-insensitive)."""
    TeamRegistration = apps.get_model("club", "TeamRegistration")
    seen = {}
    # Oldest first so the first encounter is the keeper.
    for reg in TeamRegistration.objects.order_by("submitted_at", "id"):
        key = (reg.team_name or "").strip().lower()
        if not key:
            continue
        if key in seen:
            reg.delete()
        else:
            seen[key] = reg.pk


class Migration(migrations.Migration):

    dependencies = [
        ("club", "0014_clubinfo_email_help_text"),
    ]

    operations = [
        migrations.RunPython(dedupe_team_names, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="teamregistration",
            name="team_name",
            field=models.CharField(
                help_text="Unique team name — each team may register only once.",
                max_length=120,
                unique=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="teamregistration",
            constraint=models.UniqueConstraint(
                django.db.models.functions.Lower("team_name"),
                name="uniq_teamregistration_team_name_ci",
            ),
        ),
    ]

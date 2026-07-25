import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("club", "0010_match_group_help_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="stage",
            field=models.CharField(
                choices=[
                    ("GROUP", "Group stage"),
                    ("R16", "Round of 16"),
                    ("QF", "Quarter-finals"),
                    ("SF", "Semi-finals"),
                    ("THIRD", "Third-place play-off"),
                    ("FINAL", "Final"),
                ],
                default="GROUP",
                help_text="Group stage or knockout round (World Cup format).",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="match",
            name="bracket_order",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Order within a knockout round (1 = first match, etc.).",
            ),
        ),
        migrations.AlterField(
            model_name="match",
            name="away_team",
            field=models.CharField(
                help_text="Away side. For group games, pick from the group's teams.",
                max_length=120,
            ),
        ),
        migrations.AlterField(
            model_name="match",
            name="group",
            field=models.ForeignKey(
                blank=True,
                help_text="Group stage only — which World Cup group table this "
                "result updates. Leave empty for knockout matches.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="matches",
                to="club.competitiongroup",
            ),
        ),
        migrations.AlterField(
            model_name="match",
            name="home_team",
            field=models.CharField(
                help_text="Home side. For group games, pick from the group's teams.",
                max_length=120,
            ),
        ),
        migrations.AlterModelOptions(
            name="match",
            options={
                "ordering": ["match_date", "match_time", "bracket_order"],
                "verbose_name_plural": "Matches",
            },
        ),
    ]

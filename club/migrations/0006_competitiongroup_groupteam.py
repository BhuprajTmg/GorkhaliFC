# Generated manually for World Cup–style group standings

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("club", "0005_match_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompetitionGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(help_text='e.g. "Group A".', max_length=80),
                ),
                (
                    "season",
                    models.CharField(
                        blank=True,
                        help_text='Optional label, e.g. "Darwin Cup 2026".',
                        max_length=120,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Only the active group is shown on the public schedule.",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="GroupTeam",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                (
                    "is_club",
                    models.BooleanField(
                        default=False,
                        help_text="Highlight this row as Gurkhali FC on the public table.",
                    ),
                ),
                ("played", models.PositiveSmallIntegerField(default=0)),
                ("won", models.PositiveSmallIntegerField(default=0)),
                ("drawn", models.PositiveSmallIntegerField(default=0)),
                ("lost", models.PositiveSmallIntegerField(default=0)),
                ("goals_for", models.PositiveSmallIntegerField(default=0)),
                ("goals_against", models.PositiveSmallIntegerField(default=0)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="teams",
                        to="club.competitiongroup",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "unique_together": {("group", "name")},
            },
        ),
    ]

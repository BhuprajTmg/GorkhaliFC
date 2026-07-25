from django.db import migrations, models


def create_default_knockout(apps, schema_editor):
    KnockoutBracket = apps.get_model("club", "KnockoutBracket")
    if not KnockoutBracket.objects.exists():
        KnockoutBracket.objects.create(
            name="Knockout Stage",
            season="Darwin Cup 2026",
            is_active=True,
            include_third_place=True,
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("club", "0011_match_knockout_stage"),
    ]

    operations = [
        migrations.CreateModel(
            name="KnockoutBracket",
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
                ("name", models.CharField(default="Knockout Stage", max_length=120)),
                (
                    "season",
                    models.CharField(
                        blank=True,
                        help_text='e.g. "Darwin Cup 2026".',
                        max_length=120,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Show this knockout on the public schedule when fixtures exist.",
                    ),
                ),
                (
                    "include_third_place",
                    models.BooleanField(
                        default=True,
                        help_text="Create a 3rd-place play-off alongside the Final.",
                    ),
                ),
                (
                    "start_date",
                    models.DateField(
                        blank=True,
                        help_text="First knockout matchday. Defaults to 7 days from today.",
                        null=True,
                    ),
                ),
                (
                    "generated_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Set automatically when fixtures are generated.",
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "Knockout",
                "verbose_name_plural": "Knockout",
                "ordering": ["-is_active", "name"],
            },
        ),
        migrations.RunPython(create_default_knockout, noop),
    ]

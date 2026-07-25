from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("club", "0006_competitiongroup_groupteam"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="finished_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Set automatically when status becomes Finished. Used to "
                "keep the result visible for a few minutes on the public site.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="competitiongroup",
            name="is_active",
            field=models.BooleanField(
                default=True,
                help_text="Active groups (up to four) appear in the Schedule tables grid.",
            ),
        ),
        migrations.AlterField(
            model_name="groupteam",
            name="drawn",
            field=models.PositiveSmallIntegerField(
                default=0, help_text="Auto-updated from finished matches."
            ),
        ),
        migrations.AlterField(
            model_name="groupteam",
            name="goals_against",
            field=models.PositiveSmallIntegerField(
                default=0, help_text="Auto-updated from finished matches."
            ),
        ),
        migrations.AlterField(
            model_name="groupteam",
            name="goals_for",
            field=models.PositiveSmallIntegerField(
                default=0, help_text="Auto-updated from finished matches."
            ),
        ),
        migrations.AlterField(
            model_name="groupteam",
            name="lost",
            field=models.PositiveSmallIntegerField(
                default=0, help_text="Auto-updated from finished matches."
            ),
        ),
        migrations.AlterField(
            model_name="groupteam",
            name="name",
            field=models.CharField(
                help_text="Must match the Match opponent name for score sync.",
                max_length=120,
            ),
        ),
        migrations.AlterField(
            model_name="groupteam",
            name="played",
            field=models.PositiveSmallIntegerField(
                default=0, help_text="Auto-updated from finished matches."
            ),
        ),
        migrations.AlterField(
            model_name="groupteam",
            name="won",
            field=models.PositiveSmallIntegerField(
                default=0, help_text="Auto-updated from finished matches."
            ),
        ),
        migrations.AlterField(
            model_name="match",
            name="status",
            field=models.CharField(
                choices=[
                    ("SCHEDULED", "Scheduled"),
                    ("LIVE", "Live now"),
                    ("FINISHED", "Finished"),
                ],
                default="SCHEDULED",
                help_text="Set to 'Live now' on match day to show it at the top of "
                "the schedule with a live indicator and score. Set to 'Finished' "
                "with the final score to sync the group table and briefly show the "
                "result on the site.",
                max_length=10,
            ),
        ),
    ]

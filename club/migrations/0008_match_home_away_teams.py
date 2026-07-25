from django.db import migrations, models
import django.db.models.deletion


def migrate_opponent_to_home_away(apps, schema_editor):
    Match = apps.get_model("club", "Match")
    ClubInfo = apps.get_model("club", "ClubInfo")
    GroupTeam = apps.get_model("club", "GroupTeam")
    CompetitionGroup = apps.get_model("club", "CompetitionGroup")

    club = ClubInfo.objects.first()
    club_name = club.name if club else "Gurkhali FC"

    for match in Match.objects.all():
        opponent = (match.opponent or "").strip() or "TBD"
        if match.is_home:
            match.home_team = club_name
            match.away_team = opponent
        else:
            match.home_team = opponent
            match.away_team = club_name

        # Attach shared group when both names appear together.
        home_groups = set(
            GroupTeam.objects.filter(name__iexact=match.home_team).values_list(
                "group_id", flat=True
            )
        )
        away_groups = set(
            GroupTeam.objects.filter(name__iexact=match.away_team).values_list(
                "group_id", flat=True
            )
        )
        shared = home_groups & away_groups
        if len(shared) == 1:
            match.group = CompetitionGroup.objects.filter(pk=shared.pop()).first()

        # Unblock standings sync for finished rows with a blank score.
        if match.status == "FINISHED":
            if match.home_score is None:
                match.home_score = 0
            if match.away_score is None:
                match.away_score = 0

        match.save()


def noop_reverse(apps, schema_editor):
    pass


def resync_standings(apps, schema_editor):
    from club.standings import recalculate_all_group_standings

    recalculate_all_group_standings()


class Migration(migrations.Migration):

    dependencies = [
        ("club", "0007_match_finished_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="home_team",
            field=models.CharField(
                default="",
                help_text="Home side. Must match a group team name for table sync.",
                max_length=120,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="match",
            name="away_team",
            field=models.CharField(
                default="",
                help_text="Away side. Must match a group team name for table sync.",
                max_length=120,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="match",
            name="group",
            field=models.ForeignKey(
                blank=True,
                help_text="Which World Cup group table this result updates. "
                "Both team names should exist in that group.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="matches",
                to="club.competitiongroup",
            ),
        ),
        migrations.RunPython(migrate_opponent_to_home_away, noop_reverse),
        migrations.RemoveField(model_name="match", name="opponent"),
        migrations.RemoveField(model_name="match", name="is_home"),
        migrations.AlterModelOptions(
            name="match",
            options={"ordering": ["match_date", "match_time"], "verbose_name_plural": "Matches"},
        ),
        migrations.AlterField(
            model_name="groupteam",
            name="name",
            field=models.CharField(
                help_text="Must match Match home/away team names for score sync.",
                max_length=120,
            ),
        ),
        migrations.AlterField(
            model_name="match",
            name="finished_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Set automatically when status becomes Finished.",
                null=True,
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
                help_text="Set to 'Live now' on match day, then 'Finished' with "
                "both scores filled in to sync the group table.",
                max_length=10,
            ),
        ),
        migrations.RunPython(resync_standings, noop_reverse),
    ]

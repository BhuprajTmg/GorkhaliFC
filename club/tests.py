import datetime

from django.test import TestCase
from django.utils import timezone

from club.models import ClubInfo, CompetitionGroup, GroupTeam, Match
from club.schedule import FINISHED_VISIBLE_MINUTES, build_match_schedule
from club.standings import recalculate_group_standings


class MatchScheduleTests(TestCase):
    def _create(self, home, away, day, status=Match.Status.SCHEDULED, **extra):
        return Match.objects.create(
            home_team=home,
            away_team=away,
            match_date=datetime.date(2026, 8, day),
            match_time=datetime.time(18, 0),
            status=status,
            **extra,
        )

    def test_shows_next_and_up_to_four_more_upcoming(self):
        matches = [
            self._create("Gurkhali FC", f"Team {i}", i + 1) for i in range(7)
        ]

        schedule = build_match_schedule()

        self.assertEqual(schedule["next_match"], matches[0])
        self.assertEqual(schedule["upcoming_matches"], matches[1:5])
        self.assertEqual(len(schedule["upcoming_matches"]), 4)

    def test_finished_visible_only_within_window(self):
        now = timezone.now()
        recent = self._create(
            "Gurkhali FC",
            "Darwin FC",
            8,
            status=Match.Status.FINISHED,
            home_score=2,
            away_score=1,
        )
        Match.objects.filter(pk=recent.pk).update(
            finished_at=now - datetime.timedelta(minutes=1)
        )

        stale = self._create(
            "Gurkhali FC",
            "Casuarina SC",
            9,
            status=Match.Status.FINISHED,
            home_score=0,
            away_score=0,
        )
        Match.objects.filter(pk=stale.pk).update(
            finished_at=now
            - datetime.timedelta(minutes=FINISHED_VISIBLE_MINUTES + 1)
        )

        schedule = build_match_schedule(now=now)
        past_ids = [m.pk for m in schedule["past_matches"]]

        self.assertIn(recent.pk, past_ids)
        self.assertNotIn(stale.pk, past_ids)


class GroupStandingsSyncTests(TestCase):
    def setUp(self):
        ClubInfo.objects.create(name="Gurkhali FC", founded_year=2023)
        self.group = CompetitionGroup.objects.create(
            name="Group A", season="Darwin Cup 2026", is_active=True
        )
        self.gurkhali = GroupTeam.objects.create(
            group=self.group, name="Gurkhali FC", is_club=True
        )
        self.darwin = GroupTeam.objects.create(group=self.group, name="Darwin FC")
        self.casuarina = GroupTeam.objects.create(
            group=self.group, name="Casuarina SC"
        )
        GroupTeam.objects.create(group=self.group, name="Palmerston FC")

    def test_finished_match_updates_both_teams(self):
        Match.objects.create(
            home_team="Gurkhali FC",
            away_team="Darwin FC",
            group=self.group,
            match_date=datetime.date(2026, 7, 26),
            match_time=datetime.time(18, 0),
            status=Match.Status.FINISHED,
            home_score=2,
            away_score=1,
        )

        self.gurkhali.refresh_from_db()
        self.darwin.refresh_from_db()
        self.casuarina.refresh_from_db()

        self.assertEqual(self.gurkhali.played, 1)
        self.assertEqual(self.gurkhali.won, 1)
        self.assertEqual(self.gurkhali.goals_for, 2)
        self.assertEqual(self.gurkhali.goals_against, 1)
        self.assertEqual(self.gurkhali.points, 3)

        self.assertEqual(self.darwin.played, 1)
        self.assertEqual(self.darwin.lost, 1)
        self.assertEqual(self.darwin.goals_for, 1)
        self.assertEqual(self.darwin.goals_against, 2)
        self.assertEqual(self.casuarina.played, 0)

    def test_blank_away_score_on_finished_defaults_to_zero_and_syncs(self):
        """Regression: admin left away score blank — must still sync."""
        match = Match(
            home_team="Gurkhali FC",
            away_team="Darwin FC",
            group=self.group,
            match_date=datetime.date(2026, 7, 26),
            status=Match.Status.FINISHED,
            home_score=1,
            away_score=None,
        )
        match.save()

        self.gurkhali.refresh_from_db()
        self.darwin.refresh_from_db()
        self.assertEqual(match.away_score, 0)
        self.assertEqual(self.gurkhali.won, 1)
        self.assertEqual(self.darwin.lost, 1)

    def test_non_club_group_match_updates_table(self):
        Match.objects.create(
            home_team="Darwin FC",
            away_team="Casuarina SC",
            group=self.group,
            match_date=datetime.date(2026, 7, 27),
            status=Match.Status.FINISHED,
            home_score=3,
            away_score=1,
        )
        self.darwin.refresh_from_db()
        self.casuarina.refresh_from_db()
        self.gurkhali.refresh_from_db()
        self.assertEqual(self.darwin.won, 1)
        self.assertEqual(self.casuarina.lost, 1)
        self.assertEqual(self.gurkhali.played, 0)

    def test_score_edit_on_finished_match_resyncs_table(self):
        match = Match.objects.create(
            home_team="Gurkhali FC",
            away_team="Darwin FC",
            group=self.group,
            match_date=datetime.date(2026, 7, 26),
            status=Match.Status.FINISHED,
            home_score=1,
            away_score=1,
        )
        match.home_score = 3
        match.away_score = 0
        match.save()

        self.gurkhali.refresh_from_db()
        self.darwin.refresh_from_db()
        self.assertEqual(self.gurkhali.goals_for, 3)
        self.assertEqual(self.gurkhali.won, 1)
        self.assertEqual(self.darwin.goals_against, 3)
        self.assertEqual(self.darwin.lost, 1)

    def test_auto_detects_group_from_team_names(self):
        match = Match.objects.create(
            home_team="Casuarina SC",
            away_team="Gurkhali FC",
            match_date=datetime.date(2026, 7, 28),
            status=Match.Status.FINISHED,
            home_score=0,
            away_score=2,
        )
        match.refresh_from_db()
        self.assertEqual(match.group_id, self.group.pk)
        self.gurkhali.refresh_from_db()
        self.assertEqual(self.gurkhali.won, 1)

    def test_unfinished_match_does_not_affect_table(self):
        Match.objects.create(
            home_team="Gurkhali FC",
            away_team="Darwin FC",
            group=self.group,
            match_date=datetime.date(2026, 8, 1),
            status=Match.Status.SCHEDULED,
            home_score=5,
            away_score=0,
        )
        recalculate_group_standings(self.group)
        self.gurkhali.refresh_from_db()
        self.assertEqual(self.gurkhali.played, 0)

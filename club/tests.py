import datetime

from django.test import TestCase
from django.utils import timezone

from club.models import ClubInfo, CompetitionGroup, GroupTeam, Match
from club.schedule import FINISHED_VISIBLE_MINUTES, build_match_schedule
from club.standings import recalculate_group_standings


class MatchScheduleTests(TestCase):
    def _create(self, opponent, day, status=Match.Status.SCHEDULED, **extra):
        return Match.objects.create(
            opponent=opponent,
            match_date=datetime.date(2026, 8, day),
            match_time=datetime.time(18, 0),
            status=status,
            **extra,
        )

    def test_shows_next_and_up_to_four_more_upcoming(self):
        matches = [self._create(f"Team {i}", i + 1) for i in range(7)]

        schedule = build_match_schedule()

        self.assertEqual(schedule["next_match"], matches[0])
        self.assertEqual(schedule["upcoming_matches"], matches[1:5])
        self.assertEqual(len(schedule["upcoming_matches"]), 4)

    def test_finished_visible_only_within_window(self):
        now = timezone.now()
        recent = self._create(
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

    def test_live_matches_listed_separately(self):
        live = self._create(
            "Darwin FC",
            8,
            status=Match.Status.LIVE,
            home_score=1,
            away_score=0,
        )
        nxt = self._create("Casuarina SC", 15)

        schedule = build_match_schedule()
        self.assertEqual(schedule["live_matches"], [live])
        self.assertEqual(schedule["next_match"], nxt)


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
            opponent="Darwin FC",
            match_date=datetime.date(2026, 7, 26),
            match_time=datetime.time(18, 0),
            is_home=True,
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
        self.assertEqual(self.darwin.points, 0)
        self.assertEqual(self.casuarina.played, 0)

    def test_score_edit_on_finished_match_resyncs_table(self):
        match = Match.objects.create(
            opponent="Darwin FC",
            match_date=datetime.date(2026, 7, 26),
            is_home=True,
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

    def test_away_match_uses_correct_score_sides(self):
        Match.objects.create(
            opponent="Casuarina SC",
            match_date=datetime.date(2026, 7, 28),
            is_home=False,
            status=Match.Status.FINISHED,
            home_score=2,
            away_score=2,
        )
        self.gurkhali.refresh_from_db()
        self.casuarina.refresh_from_db()
        self.assertEqual(self.gurkhali.drawn, 1)
        self.assertEqual(self.gurkhali.goals_for, 2)
        self.assertEqual(self.casuarina.drawn, 1)
        self.assertEqual(self.casuarina.goals_for, 2)

    def test_unfinished_match_does_not_affect_table(self):
        Match.objects.create(
            opponent="Darwin FC",
            match_date=datetime.date(2026, 8, 1),
            status=Match.Status.SCHEDULED,
            home_score=5,
            away_score=0,
        )
        recalculate_group_standings(self.group)
        self.gurkhali.refresh_from_db()
        self.assertEqual(self.gurkhali.played, 0)

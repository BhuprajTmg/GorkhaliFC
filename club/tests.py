import datetime

from django.test import TestCase

from club.models import Match
from club.schedule import build_match_schedule


class MatchScheduleRevealTests(TestCase):
    def _create(self, opponent, day, status=Match.Status.SCHEDULED, **extra):
        return Match.objects.create(
            opponent=opponent,
            match_date=datetime.date(2026, 8, day),
            match_time=datetime.time(18, 0),
            status=status,
            **extra,
        )

    def test_only_first_scheduled_shows_when_none_finished(self):
        first = self._create("Darwin FC", 8)
        self._create("Casuarina SC", 15)
        self._create("Palmerston FC", 22)

        schedule = build_match_schedule()

        self.assertEqual(schedule["next_match"], first)
        self.assertEqual(schedule["upcoming_matches"], [])
        self.assertEqual(schedule["live_matches"], [])
        self.assertEqual(schedule["past_matches"], [])

    def test_next_advances_only_after_previous_finished(self):
        first = self._create(
            "Darwin FC",
            8,
            status=Match.Status.FINISHED,
            home_score=2,
            away_score=1,
        )
        second = self._create("Casuarina SC", 15)
        self._create("Palmerston FC", 22)

        schedule = build_match_schedule()

        self.assertEqual(schedule["next_match"], second)
        self.assertEqual(schedule["upcoming_matches"], [])
        self.assertEqual(list(schedule["past_matches"]), [first])

    def test_live_match_blocks_next_until_finished(self):
        live = self._create(
            "Darwin FC",
            8,
            status=Match.Status.LIVE,
            home_score=1,
            away_score=0,
        )
        self._create("Casuarina SC", 15)

        schedule = build_match_schedule()

        self.assertEqual(schedule["live_matches"], [live])
        self.assertIsNone(schedule["next_match"])
        self.assertEqual(schedule["upcoming_matches"], [])

    def test_next_appears_after_live_match_marked_finished(self):
        self._create(
            "Darwin FC",
            8,
            status=Match.Status.FINISHED,
            home_score=1,
            away_score=0,
        )
        second = self._create("Casuarina SC", 15)

        schedule = build_match_schedule()

        self.assertEqual(schedule["next_match"], second)
        self.assertEqual(schedule["live_matches"], [])

    def test_empty_schedule(self):
        schedule = build_match_schedule()
        self.assertIsNone(schedule["next_match"])
        self.assertEqual(schedule["upcoming_matches"], [])
        self.assertEqual(schedule["live_matches"], [])
        self.assertEqual(schedule["past_matches"], [])

    def test_sequential_finish_walks_the_queue(self):
        m1 = self._create("A", 1)
        m2 = self._create("B", 8)
        m3 = self._create("C", 15)

        self.assertEqual(build_match_schedule()["next_match"], m1)

        m1.status = Match.Status.FINISHED
        m1.home_score = 1
        m1.away_score = 0
        m1.save()
        self.assertEqual(build_match_schedule()["next_match"], m2)

        m2.status = Match.Status.FINISHED
        m2.home_score = 0
        m2.away_score = 0
        m2.save()
        self.assertEqual(build_match_schedule()["next_match"], m3)

        m3.status = Match.Status.FINISHED
        m3.home_score = 3
        m3.away_score = 1
        m3.save()
        schedule = build_match_schedule()
        self.assertIsNone(schedule["next_match"])
        self.assertEqual(len(schedule["past_matches"]), 3)

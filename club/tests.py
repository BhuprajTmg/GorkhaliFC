import datetime

from django.test import TestCase
from django.utils import timezone

from club.forms import MatchAdminForm
from club.group_fixtures import (
    generate_group_stage_fixtures,
    world_cup_group_rounds,
)
from club.knockout import (
    all_group_stages_complete,
    generate_knockout_bracket,
    group_stage_progress,
    planned_first_round_pairings,
    qualifier_rows,
    qualifiers_from_groups,
    reset_knockout_fixtures,
)
from club.models import (
    ClubInfo,
    CompetitionGroup,
    GroupTeam,
    KnockoutBracket,
    Match,
    TeamRegistration,
)
from club.schedule import (
    FINISHED_VISIBLE_MINUTES,
    build_knockout_bracket_display,
    build_match_schedule,
)
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

    def test_schedule_includes_knockout_bracket_tree(self):
        schedule = build_match_schedule()
        self.assertIn("knockout_bracket", schedule)
        self.assertIn("columns", schedule["knockout_bracket"])


class KnockoutBracketDisplayTests(TestCase):
    def setUp(self):
        ClubInfo.objects.create(name="Gurkhali FC", founded_year=2023)
        for letter in "ABCD":
            group = CompetitionGroup.objects.create(
                name=f"Group {letter}",
                season="Darwin Cup 2026",
                is_active=True,
            )
            for i in range(1, 5):
                GroupTeam.objects.create(
                    group=group,
                    name=f"{letter}{i}",
                    played=3,
                    won=4 - i,
                    drawn=0,
                    lost=i - 1,
                    goals_for=10 - i,
                    goals_against=i,
                )

    def _finish_all_group_stages(self):
        for group in CompetitionGroup.objects.filter(is_active=True):
            teams = list(group.teams.all())
            Match.objects.create(
                home_team=teams[0].name,
                away_team=teams[-1].name,
                group=group,
                stage=Match.Stage.GROUP,
                match_date=datetime.date(2026, 8, 1),
                status=Match.Status.FINISHED,
                home_score=1,
                away_score=0,
            )

    def test_hides_bracket_until_group_stage_complete(self):
        Match.objects.create(
            home_team="A1",
            away_team="B2",
            stage=Match.Stage.QF,
            bracket_order=1,
            match_date=datetime.date(2026, 8, 20),
            status=Match.Status.SCHEDULED,
        )
        bracket = build_knockout_bracket_display()
        self.assertFalse(bracket["group_stage_complete"])
        self.assertFalse(bracket["visible"])
        self.assertEqual(bracket["columns"], [])

    def test_preview_shows_qf_sf_final_columns_after_groups_finish(self):
        self._finish_all_group_stages()
        bracket = build_knockout_bracket_display()
        stages = [col["stage"] for col in bracket["columns"]]
        self.assertEqual(
            stages,
            [Match.Stage.QF, Match.Stage.SF, Match.Stage.FINAL],
        )
        self.assertEqual(len(bracket["columns"][0]["slots"]), 4)
        self.assertTrue(bracket["visible"])

    def test_real_qf_fixtures_appear_in_bracket(self):
        self._finish_all_group_stages()
        Match.objects.create(
            home_team="A1",
            away_team="B2",
            stage=Match.Stage.QF,
            bracket_order=1,
            match_date=datetime.date(2026, 8, 20),
            status=Match.Status.SCHEDULED,
        )
        bracket = build_knockout_bracket_display()
        qf = bracket["columns"][0]
        self.assertEqual(qf["stage"], Match.Stage.QF)
        self.assertFalse(qf["slots"][0]["is_placeholder"])
        self.assertEqual(qf["slots"][0]["home"], "A1")
        self.assertTrue(bracket["has_fixtures"])


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


class MatchGroupAutoAddTests(TestCase):
    def setUp(self):
        ClubInfo.objects.create(name="Gurkhali FC", founded_year=2023)
        self.group = CompetitionGroup.objects.create(
            name="Group A", season="Darwin Cup 2026", is_active=True
        )
        for name in ("Chillax 1", "Gurkhali FC Red"):
            TeamRegistration.objects.create(
                tournament_name="Darwin Cup 2026",
                team_name=name,
                manager_name="Manager",
                phone="0400000000",
                email=f"{name.replace(' ', '').lower()}@example.com",
                agreed_to_rules=True,
                status=TeamRegistration.Status.APPROVED,
            )

    def test_saving_match_with_group_adds_missing_teams(self):
        # Group starts empty / with unrelated names — match should still save.
        GroupTeam.objects.create(group=self.group, name="Darwin FC")

        match = Match.objects.create(
            home_team="Chillax 1",
            away_team="Gurkhali FC Red",
            group=self.group,
            match_date=datetime.date(2026, 7, 25),
            status=Match.Status.SCHEDULED,
        )

        names = set(self.group.teams.values_list("name", flat=True))
        self.assertIn("Chillax 1", names)
        self.assertIn("Gurkhali FC Red", names)
        self.assertEqual(match.group_id, self.group.pk)

    def test_finished_match_syncs_after_auto_add(self):
        Match.objects.create(
            home_team="Chillax 1",
            away_team="Gurkhali FC Red",
            group=self.group,
            match_date=datetime.date(2026, 7, 25),
            status=Match.Status.FINISHED,
            home_score=1,
            away_score=2,
        )
        home = GroupTeam.objects.get(group=self.group, name="Chillax 1")
        away = GroupTeam.objects.get(group=self.group, name="Gurkhali FC Red")
        self.assertEqual(home.lost, 1)
        self.assertEqual(away.won, 1)
        self.assertEqual(away.goals_for, 2)


class WorldCupFixtureGeneratorTests(TestCase):
    def setUp(self):
        ClubInfo.objects.create(
            name="Gurkhali FC", founded_year=2023, home_ground="Gardens Oval, Darwin"
        )
        self.group = CompetitionGroup.objects.create(
            name="Group A", season="Darwin Cup 2026", is_active=True
        )
        for name in ("Alpha FC", "Bravo SC", "Charlie United", "Delta FC"):
            GroupTeam.objects.create(group=self.group, name=name)

    def test_four_teams_create_six_fixtures_across_three_rounds(self):
        rounds = world_cup_group_rounds(
            ["Alpha FC", "Bravo SC", "Charlie United", "Delta FC"]
        )
        self.assertEqual(len(rounds), 3)
        self.assertTrue(all(len(r) == 2 for r in rounds))

        result = generate_group_stage_fixtures(
            self.group, start_date=datetime.date(2026, 8, 1)
        )
        self.assertEqual(len(result.created), 6)
        self.assertEqual(len(result.skipped), 0)
        self.assertEqual(Match.objects.filter(group=self.group).count(), 6)

        # Every pair appears exactly once (order-independent).
        pairs = set()
        for match in Match.objects.filter(group=self.group):
            pairs.add(frozenset({match.home_team, match.away_team}))
        self.assertEqual(len(pairs), 6)

    def test_rerun_skips_existing_pairings(self):
        generate_group_stage_fixtures(
            self.group, start_date=datetime.date(2026, 8, 1)
        )
        result = generate_group_stage_fixtures(
            self.group, start_date=datetime.date(2026, 9, 1)
        )
        self.assertEqual(len(result.created), 0)
        self.assertEqual(len(result.skipped), 6)
        self.assertEqual(Match.objects.filter(group=self.group).count(), 6)

    def test_needs_at_least_two_teams(self):
        empty = CompetitionGroup.objects.create(name="Group Z", is_active=True)
        result = generate_group_stage_fixtures(empty)
        self.assertEqual(result.created, [])
        self.assertTrue(result.errors)


class KnockoutBracketTests(TestCase):
    def setUp(self):
        ClubInfo.objects.create(name="Gurkhali FC", founded_year=2023)
        self.groups = []
        for letter, teams in [
            ("A", ["A1", "A2", "A3", "A4"]),
            ("B", ["B1", "B2", "B3", "B4"]),
            ("C", ["C1", "C2", "C3", "C4"]),
            ("D", ["D1", "D2", "D3", "D4"]),
        ]:
            group = CompetitionGroup.objects.create(
                name=f"Group {letter}", season="Cup", is_active=True
            )
            for index, name in enumerate(teams):
                GroupTeam.objects.create(
                    group=group,
                    name=name,
                    played=3,
                    won=3 - index,
                    drawn=0,
                    lost=index,
                    goals_for=6 - index,
                    goals_against=index,
                )
            self.groups.append(group)

    def test_qualifiers_top_two(self):
        q = qualifiers_from_groups(self.groups)
        self.assertEqual(q["1A"], "A1")
        self.assertEqual(q["2A"], "A2")
        self.assertEqual(q["1B"], "B1")

    def test_generate_knockout_creates_qf_sf_final(self):
        # Mark group stage complete so require_group_stage_complete passes.
        for group in self.groups:
            Match.objects.create(
                home_team=group.teams.first().name,
                away_team=group.teams.last().name,
                group=group,
                stage=Match.Stage.GROUP,
                match_date=datetime.date(2026, 8, 1),
                status=Match.Status.FINISHED,
                home_score=1,
                away_score=0,
            )
        self.assertTrue(all_group_stages_complete(self.groups))

        result = generate_knockout_bracket(
            start_date=datetime.date(2026, 9, 1),
            include_third_place=True,
            require_group_stage_complete=True,
        )
        self.assertFalse(result.errors, result.errors)
        stages = {m.stage for m in result.created}
        self.assertIn(Match.Stage.QF, stages)
        self.assertIn(Match.Stage.SF, stages)
        self.assertIn(Match.Stage.FINAL, stages)
        self.assertIn(Match.Stage.THIRD, stages)
        self.assertEqual(
            Match.objects.filter(stage=Match.Stage.QF).count(), 4
        )

    def test_blocks_generate_until_group_stage_finished(self):
        result = generate_knockout_bracket(require_group_stage_complete=True)
        self.assertTrue(result.errors)
        self.assertEqual(Match.objects.exclude(stage=Match.Stage.GROUP).count(), 0)

    def test_hides_qualifier_team_names_until_group_finished(self):
        rows = qualifier_rows(self.groups)
        self.assertTrue(all(row["first"] == "TBD" for row in rows))
        stage, pairings = planned_first_round_pairings(self.groups)
        self.assertEqual(stage, Match.Stage.QF)
        self.assertTrue(all(not p["teams_revealed"] for p in pairings))
        self.assertEqual(pairings[0]["home"], "1A")

    def test_reset_removes_knockout_fixtures(self):
        Match.objects.create(
            home_team="A1",
            away_team="B2",
            stage=Match.Stage.QF,
            bracket_order=1,
            match_date=datetime.date(2026, 9, 1),
            status=Match.Status.SCHEDULED,
        )
        hub = KnockoutBracket.get_solo()
        hub.generated_at = timezone.now()
        hub.save(update_fields=["generated_at"])

        result = reset_knockout_fixtures()
        self.assertTrue(result.advanced)
        self.assertEqual(Match.objects.exclude(stage=Match.Stage.GROUP).count(), 0)
        hub.refresh_from_db()
        self.assertIsNone(hub.generated_at)

    def test_knockout_hub_exists(self):
        hub = KnockoutBracket.get_solo()
        self.assertEqual(hub.name, "Knockout Stage")


class GroupFilteredMatchDropdownTests(TestCase):
    def setUp(self):
        self.group_a = CompetitionGroup.objects.create(name="Group A", is_active=True)
        self.group_b = CompetitionGroup.objects.create(name="Group B", is_active=True)
        for name in ("Chillax 1", "Gurkhali FC Red", "Darwin FC"):
            GroupTeam.objects.create(group=self.group_a, name=name)
        GroupTeam.objects.create(group=self.group_b, name="Nightcliff FC")
        GroupTeam.objects.create(group=self.group_b, name="Mindil Beach SC")

    def test_home_away_only_list_selected_group_teams(self):
        form = MatchAdminForm(data={"group": self.group_a.pk})
        # Bound form resolves group from POST data for choices.
        form.is_valid()
        choice_values = [
            value for value, label in form.fields["home_team"].choices if value
        ]
        self.assertEqual(
            sorted(choice_values),
            ["Chillax 1", "Darwin FC", "Gurkhali FC Red"],
        )
        self.assertNotIn("Nightcliff FC", choice_values)

    def test_rejects_team_from_another_group(self):
        form = MatchAdminForm(
            data={
                "group": self.group_a.pk,
                "home_team": "Chillax 1",
                "away_team": "Nightcliff FC",
                "match_date": "2026-08-01",
                "status": Match.Status.SCHEDULED,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("away_team", form.errors)

    def test_requires_group(self):
        form = MatchAdminForm(
            data={
                "home_team": "Chillax 1",
                "away_team": "Darwin FC",
                "match_date": "2026-08-01",
                "status": Match.Status.SCHEDULED,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors)

    def test_teams_for_group_admin_endpoint(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        User = get_user_model()
        admin_user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        self.client.force_login(admin_user)
        url = reverse("admin:club_match_teams_for_group")
        response = self.client.get(url, {"group_id": self.group_b.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(response.json()["teams"]),
            ["Mindil Beach SC", "Nightcliff FC"],
        )

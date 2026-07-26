import datetime

from django.test import TestCase
from django.utils import timezone

from club.forms import MatchAdminForm
from club.group_fixtures import (
    generate_group_stage_fixtures,
    world_cup_group_rounds,
)
from club.knockout import (
    advance_knockout_winners,
    all_group_stages_complete,
    ensure_knockout_progress,
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
from club.context_processors import schedule_nav
from club.schedule import (
    FINISHED_VISIBLE_MINUTES,
    build_knockout_bracket_display,
    build_match_schedule,
)
from club.standings import recalculate_group_standings


class ScheduleReadyTests(TestCase):
    def test_schedule_hidden_until_groups_have_teams(self):
        self.assertFalse(schedule_nav(None)["schedule_ready"])
        group = CompetitionGroup.objects.create(name="Group A", is_active=True)
        self.assertFalse(schedule_nav(None)["schedule_ready"])
        GroupTeam.objects.create(group=group, name="Chillax 1")
        self.assertTrue(schedule_nav(None)["schedule_ready"])


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

    def test_next_and_upcoming_use_knockout_after_group_stage(self):
        ClubInfo.objects.create(name="Gurkhali FC", founded_year=2023)
        hub = KnockoutBracket.get_solo()
        hub.start_date = datetime.date(2026, 9, 1)
        hub.save(update_fields=["start_date"])

        # Create every group first so auto-schedule waits for all four.
        groups = []
        for letter in "ABCD":
            group = CompetitionGroup.objects.create(
                name=f"Group {letter}", season="Cup", is_active=True
            )
            for index in range(4):
                GroupTeam.objects.create(
                    group=group,
                    name=f"{letter}{index + 1}",
                    played=1,
                    won=1 if index == 0 else 0,
                    lost=0 if index == 0 else 1,
                )
            groups.append(group)

        for letter, group in zip("ABCD", groups):
            Match.objects.create(
                home_team=f"{letter}1",
                away_team=f"{letter}4",
                group=group,
                stage=Match.Stage.GROUP,
                match_date=datetime.date(2026, 8, 1),
                status=Match.Status.FINISHED,
                home_score=2,
                away_score=0,
            )

        # Finishing the last group match auto-schedules quarter-finals.
        qf = list(
            Match.objects.filter(stage=Match.Stage.QF).order_by("bracket_order", "pk")
        )
        self.assertEqual(len(qf), 4)
        self.assertEqual(Match.objects.filter(stage=Match.Stage.SF).count(), 0)
        # Placeholder SF shells must not appear in Next/Upcoming.
        Match.objects.create(
            home_team="Winner QF1",
            away_team="Winner QF2",
            stage=Match.Stage.SF,
            bracket_order=1,
            match_date=datetime.date(2026, 9, 5),
            status=Match.Status.SCHEDULED,
        )

        schedule = build_match_schedule()
        self.assertEqual(schedule["next_match"], qf[0])
        self.assertEqual(schedule["upcoming_matches"], qf[1:5])
        self.assertTrue(
            all(m.stage == Match.Stage.QF for m in schedule["upcoming_matches"])
        )
        self.assertNotIn(
            "Winner QF1",
            [m.home_team for m in [schedule["next_match"], *schedule["upcoming_matches"]]],
        )

    def test_ensure_creates_qf_when_groups_done_but_bracket_missing(self):
        ClubInfo.objects.create(name="Gurkhali FC", founded_year=2023)
        hub = KnockoutBracket.get_solo()
        hub.start_date = datetime.date(2026, 9, 10)
        hub.save(update_fields=["start_date"])

        groups = []
        for letter in "ABCD":
            group = CompetitionGroup.objects.create(
                name=f"Group {letter}", season="Cup", is_active=True
            )
            for index in range(4):
                GroupTeam.objects.create(
                    group=group,
                    name=f"{letter}{index + 1}",
                    played=1,
                    won=1 if index == 0 else 0,
                    lost=0 if index == 0 else 1,
                )
            groups.append(group)

        # Finish groups without leaving auto-created knockout fixtures.
        for letter, group in zip("ABCD", groups):
            Match.objects.create(
                home_team=f"{letter}1",
                away_team=f"{letter}4",
                group=group,
                stage=Match.Stage.GROUP,
                match_date=datetime.date(2026, 8, 1),
                status=Match.Status.FINISHED,
                home_score=2,
                away_score=0,
            )
        reset_knockout_fixtures()
        self.assertEqual(Match.objects.exclude(stage=Match.Stage.GROUP).count(), 0)

        ensure_knockout_progress()
        qf = Match.objects.filter(stage=Match.Stage.QF, status=Match.Status.SCHEDULED)
        self.assertEqual(qf.count(), 4)

        schedule = build_match_schedule()
        self.assertIsNotNone(schedule["next_match"])
        self.assertEqual(schedule["next_match"].stage, Match.Stage.QF)
        self.assertEqual(len(schedule["upcoming_matches"]), 3)


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
                tournament_name="Dashain Cup 2026",
                team_name=name,
                manager_name="Manager",
                phone="0400000000",
                email=f"{name.replace(' ', '').lower()}@gmail.com",
                agreed_to_rules=True,
                status=TeamRegistration.Status.APPROVED,
                home_city="Darwin",
                experience="N/A",
                notes="N/A",
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

    def _finish_groups(self):
        # All groups already exist in setUp — finish them together so the
        # auto-scheduler sees the full 4-group tournament.
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

    def test_generate_knockout_schedules_quarter_finals_only(self):
        self._finish_groups()
        self.assertTrue(all_group_stages_complete(self.groups))

        # Reset any QF auto-created by finishing the last group match.
        reset_knockout_fixtures()

        result = generate_knockout_bracket(
            start_date=datetime.date(2026, 9, 1),
            include_third_place=True,
            require_group_stage_complete=True,
        )
        self.assertFalse(result.errors, result.errors)
        stages = {m.stage for m in result.created}
        self.assertEqual(stages, {Match.Stage.QF})
        self.assertEqual(Match.objects.filter(stage=Match.Stage.QF).count(), 4)
        self.assertEqual(Match.objects.filter(stage=Match.Stage.SF).count(), 0)
        self.assertEqual(Match.objects.filter(stage=Match.Stage.FINAL).count(), 0)

    def test_finishing_all_qf_schedules_semifinals(self):
        self._finish_groups()
        reset_knockout_fixtures()
        generate_knockout_bracket(
            start_date=datetime.date(2026, 9, 1),
            require_group_stage_complete=True,
        )
        qf_matches = list(
            Match.objects.filter(stage=Match.Stage.QF).order_by("bracket_order")
        )
        self.assertEqual(len(qf_matches), 4)

        for match in qf_matches:
            match.status = Match.Status.FINISHED
            match.home_score = 2
            match.away_score = 1
            match.save()

        sf = list(
            Match.objects.filter(stage=Match.Stage.SF).order_by("bracket_order")
        )
        self.assertEqual(len(sf), 2)
        self.assertEqual(sf[0].home_team, qf_matches[0].home_team)
        self.assertEqual(sf[0].away_team, qf_matches[1].home_team)
        self.assertEqual(sf[0].status, Match.Status.SCHEDULED)
        self.assertEqual(
            sf[0].match_date,
            datetime.date(2026, 9, 1) + datetime.timedelta(days=3),
        )
        # Final waits until semi-finals are finished.
        self.assertEqual(Match.objects.filter(stage=Match.Stage.FINAL).count(), 0)

    def test_finishing_all_sf_schedules_final_and_third(self):
        self._finish_groups()
        reset_knockout_fixtures()
        generate_knockout_bracket(
            start_date=datetime.date(2026, 9, 1),
            include_third_place=True,
            require_group_stage_complete=True,
        )
        for match in Match.objects.filter(stage=Match.Stage.QF):
            match.status = Match.Status.FINISHED
            match.home_score = 1
            match.away_score = 0
            match.save()

        sf_matches = list(
            Match.objects.filter(stage=Match.Stage.SF).order_by("bracket_order")
        )
        for match in sf_matches:
            match.status = Match.Status.FINISHED
            match.home_score = 3
            match.away_score = 1
            match.save()

        final = Match.objects.get(stage=Match.Stage.FINAL, bracket_order=1)
        third = Match.objects.get(stage=Match.Stage.THIRD, bracket_order=1)
        self.assertEqual(final.home_team, sf_matches[0].home_team)
        self.assertEqual(final.away_team, sf_matches[1].home_team)
        self.assertEqual(final.status, Match.Status.SCHEDULED)
        self.assertEqual(third.home_team, sf_matches[0].away_team)
        self.assertEqual(third.away_team, sf_matches[1].away_team)

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


class TeamRegistrationFormTests(TestCase):
    def setUp(self):
        self.club = ClubInfo.objects.create(
            name="Gurkhali FC", founded_year=2023, email="club@gmail.com"
        )

    def _base_registration_data(self, email="teammanager@gmail.com"):
        from club.forms import RegisteredPlayerFormSet, TeamRegistrationForm
        from club.models import ROSTER_SIZE

        data = {
            "form_name": "registration",
            "registration-team_name": "Himalayan United",
            "registration-manager_name": "Ram Bahadur",
            "registration-phone": "0400123456",
            "registration-email": email,
            "registration-home_city": "Darwin",
            "registration-experience": "Played local cup 2025",
            "registration-notes": "N/A",
            "registration-agreed_to_rules": "on",
            "roster-TOTAL_FORMS": str(ROSTER_SIZE),
            "roster-INITIAL_FORMS": "0",
            "roster-MIN_NUM_FORMS": str(ROSTER_SIZE),
            "roster-MAX_NUM_FORMS": str(ROSTER_SIZE),
        }
        for i in range(ROSTER_SIZE):
            data[f"roster-{i}-name"] = f"Player {i + 1}"
            data[f"roster-{i}-jersey_number"] = "" if i % 2 else str(i + 1)
            data[f"roster-{i}-id"] = ""
        return data

    def test_gmail_required(self):
        from club.forms import TeamRegistrationForm

        form = TeamRegistrationForm(
            data={
                "team_name": "Test FC",
                "manager_name": "Coach",
                "phone": "0400123456",
                "email": "coach@yahoo.com",
                "home_city": "Darwin",
                "experience": "N/A",
                "notes": "N/A",
                "agreed_to_rules": True,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_accepts_valid_gmail(self):
        from club.forms import TeamRegistrationForm

        form = TeamRegistrationForm(
            data={
                "team_name": "Test FC",
                "manager_name": "Coach",
                "phone": "0400123456",
                "email": "coach.team@gmail.com",
                "home_city": "Darwin",
                "experience": "N/A",
                "notes": "N/A",
                "agreed_to_rules": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        reg = form.save()
        self.assertEqual(reg.tournament_name, "Dashain Cup 2026")
        self.assertEqual(reg.division, TeamRegistration.Division.OPEN_7A)

    def test_all_twelve_player_names_required(self):
        from club.forms import RegisteredPlayerFormSet
        from club.models import ROSTER_SIZE

        data = {
            "players-TOTAL_FORMS": str(ROSTER_SIZE),
            "players-INITIAL_FORMS": "0",
            "players-MIN_NUM_FORMS": str(ROSTER_SIZE),
            "players-MAX_NUM_FORMS": str(ROSTER_SIZE),
        }
        for i in range(ROSTER_SIZE):
            data[f"players-{i}-name"] = f"Player {i + 1}" if i < 11 else ""
            data[f"players-{i}-jersey_number"] = ""
            data[f"players-{i}-id"] = ""

        formset = RegisteredPlayerFormSet(data, instance=TeamRegistration(), prefix="players")
        self.assertFalse(formset.is_valid())

    def test_submit_sends_confirmation_email(self):
        from django.core import mail

        response = self.client.post("/", self._base_registration_data(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TeamRegistration.objects.count(), 1)
        reg = TeamRegistration.objects.get()
        self.assertEqual(reg.player_count, 12)
        self.assertEqual(reg.tournament_name, "Dashain Cup 2026")

        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(any("Registration received" in s for s in subjects))
        confirm = next(m for m in mail.outbox if "Registration received" in m.subject)
        self.assertEqual(confirm.to, ["teammanager@gmail.com"])
        self.assertIn(
            "Your team registration is being reviewed and when approved you will get notified.",
            confirm.body,
        )

    def test_sixteenth_approval_emails_schedules(self):
        from django.core import mail

        from club.models import APPROVED_TEAMS_FOR_SCHEDULE

        for i in range(APPROVED_TEAMS_FOR_SCHEDULE - 1):
            TeamRegistration.objects.create(
                tournament_name="Dashain Cup 2026",
                team_name=f"Team {i + 1}",
                manager_name="Manager",
                phone="0400000000",
                email=f"team{i + 1}@gmail.com",
                agreed_to_rules=True,
                status=TeamRegistration.Status.APPROVED,
                home_city="Darwin",
                experience="N/A",
                notes="N/A",
            )

        pending = TeamRegistration.objects.create(
            tournament_name="Dashain Cup 2026",
            team_name="Team 16",
            manager_name="Manager",
            phone="0400000000",
            email="team16@gmail.com",
            agreed_to_rules=True,
            status=TeamRegistration.Status.PENDING,
            home_city="Darwin",
            experience="N/A",
            notes="N/A",
        )
        mail.outbox.clear()
        pending.status = TeamRegistration.Status.APPROVED
        pending.save()

        schedule_mails = [
            m for m in mail.outbox if "Match schedules are ready" in m.subject
        ]
        self.assertEqual(len(schedule_mails), APPROVED_TEAMS_FOR_SCHEDULE)


class EmailSenderTests(TestCase):
    def test_from_email_uses_club_name_and_smtp_user(self):
        from django.test import override_settings

        from club.emails import _from_email, email_delivery_enabled

        club = ClubInfo.objects.create(
            name="Gurkhali FC", email="club@gmail.com", founded_year=2023
        )
        with override_settings(
            EMAIL_HOST_USER="club@gmail.com",
            EMAIL_HOST_PASSWORD="abcd efgh ijkl mnop",
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
            DEFAULT_FROM_EMAIL="club@gmail.com",
        ):
            self.assertTrue(email_delivery_enabled())
            self.assertEqual(_from_email(club), "Gurkhali FC <club@gmail.com>")

    def test_from_email_falls_back_to_smtp_login_if_club_differs(self):
        from django.test import override_settings

        from club.emails import _from_email

        club = ClubInfo.objects.create(
            name="Gurkhali FC", email="other@gmail.com", founded_year=2023
        )
        with override_settings(
            EMAIL_HOST_USER="smtp.login@gmail.com",
            DEFAULT_FROM_EMAIL="smtp.login@gmail.com",
        ):
            # Gmail requires From == authenticated user.
            self.assertEqual(
                _from_email(club), "Gurkhali FC <smtp.login@gmail.com>"
            )

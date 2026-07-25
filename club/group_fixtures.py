"""Auto-generate World Cup group-stage fixtures (single round-robin).

For 4 teams this creates the classic 6 group matches. Existing home/away
pairings in the same group are skipped so the action is safe to re-run.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.db.models import Q
from django.utils import timezone

from .models import ClubInfo, CompetitionGroup, Match


@dataclass
class GenerateResult:
    created: list
    skipped: list
    errors: list


def round_robin_pairings(team_names):
    """Return balanced (home, away) pairings for a single round-robin."""
    names = [n.strip() for n in team_names if n and n.strip()]
    pairings = []
    for i, home_candidate in enumerate(names):
        for away_candidate in names[i + 1 :]:
            # Alternate home advantage so earlier alphabet teams don't
            # always host.
            if (i + names.index(away_candidate)) % 2 == 0:
                pairings.append((home_candidate, away_candidate))
            else:
                pairings.append((away_candidate, home_candidate))
    return pairings


def world_cup_group_rounds(team_names):
    """Return rounds of pairings for 4-team World Cup style (3 matchdays).

    Falls back to a flat round-robin list for other squad sizes.
    """
    names = [n.strip() for n in team_names if n and n.strip()]
    if len(names) != 4:
        # One "round" containing every pairing.
        return [round_robin_pairings(names)]

    a, b, c, d = names
    # Classic 4-team group: 3 matchdays, 2 games each.
    return [
        [(a, b), (c, d)],
        [(a, c), (d, b)],
        [(a, d), (b, c)],
    ]


def _fixture_exists(group, home, away):
    return (
        Match.objects.filter(group=group)
        .filter(
            Q(home_team__iexact=home, away_team__iexact=away)
            | Q(home_team__iexact=away, away_team__iexact=home)
        )
        .exists()
    )


def generate_group_stage_fixtures(
    group,
    *,
    start_date=None,
    days_between_rounds=3,
    match_time=None,
    venue="",
):
    """Create scheduled round-robin matches for every team in ``group``.

    Returns a GenerateResult with created/skipped Match summaries.
    """
    result = GenerateResult(created=[], skipped=[], errors=[])
    teams = list(group.teams.order_by("name"))
    if len(teams) < 2:
        result.errors.append(
            f"{group.name} needs at least 2 teams before fixtures can be generated."
        )
        return result

    team_names = [t.name for t in teams]
    rounds = world_cup_group_rounds(team_names)

    if start_date is None:
        start_date = timezone.localdate() + datetime.timedelta(days=7)
    if match_time is None:
        match_time = datetime.time(18, 0)
    if not venue:
        club = ClubInfo.objects.first()
        venue = (club.home_ground if club and club.home_ground else "") or ""

    kickoff_slot = 0  # stagger same-day double-headers by 2 hours
    for round_index, round_pairings in enumerate(rounds):
        match_date = start_date + datetime.timedelta(
            days=round_index * days_between_rounds
        )
        for home, away in round_pairings:
            if _fixture_exists(group, home, away):
                result.skipped.append(f"{home} vs {away}")
                continue

            slot_time = (
                datetime.datetime.combine(match_date, match_time)
                + datetime.timedelta(hours=2 * (kickoff_slot % 2))
            ).time()
            kickoff_slot += 1

            match = Match.objects.create(
                home_team=home,
                away_team=away,
                group=group,
                match_date=match_date,
                match_time=slot_time,
                venue=venue,
                status=Match.Status.SCHEDULED,
            )
            result.created.append(match)

    return result

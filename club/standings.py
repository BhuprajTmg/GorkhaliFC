"""Sync World Cup group tables from finished Match scores.

Each Match is Gurkhali FC vs an opponent. When a match is Finished with
scores, both the club row and the opponent row (if that opponent is in the
same CompetitionGroup) are updated. Standings are fully recalculated from
all finished scored matches so score edits stay in sync.
"""

from .models import ClubInfo, CompetitionGroup, GroupTeam, Match


def _apply_result(bucket, gf, ga):
    bucket["played"] += 1
    bucket["goals_for"] += gf
    bucket["goals_against"] += ga
    if gf > ga:
        bucket["won"] += 1
    elif gf == ga:
        bucket["drawn"] += 1
    else:
        bucket["lost"] += 1


def _empty_stats():
    return {
        "played": 0,
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "goals_for": 0,
        "goals_against": 0,
    }


def recalculate_group_standings(group):
    """Reset a group's team stats and rebuild them from finished matches."""
    teams = list(group.teams.all())
    if not teams:
        return

    by_name = {team.name.strip().lower(): team for team in teams}
    stats = {team.pk: _empty_stats() for team in teams}

    club_team = next((team for team in teams if team.is_club), None)
    if club_team is None:
        club = ClubInfo.objects.first()
        if club:
            club_team = by_name.get(club.name.strip().lower())

    if club_team is not None:
        finished_matches = Match.objects.filter(
            status=Match.Status.FINISHED,
            home_score__isnull=False,
            away_score__isnull=False,
        )
        for match in finished_matches:
            opponent = by_name.get(match.opponent.strip().lower())
            if opponent is None:
                continue
            if match.is_home:
                club_gf, club_ga = match.home_score, match.away_score
            else:
                club_gf, club_ga = match.away_score, match.home_score
            _apply_result(stats[club_team.pk], club_gf, club_ga)
            _apply_result(stats[opponent.pk], club_ga, club_gf)

    update_fields = [
        "played",
        "won",
        "drawn",
        "lost",
        "goals_for",
        "goals_against",
    ]
    for team in teams:
        values = stats[team.pk]
        for field in update_fields:
            setattr(team, field, values[field])
        team.save(update_fields=update_fields)


def recalculate_all_group_standings():
    for group in CompetitionGroup.objects.prefetch_related("teams"):
        recalculate_group_standings(group)


def sync_standings_after_match(match):
    """Recalculate every group that could be affected by this match."""
    opponent_key = (match.opponent or "").strip().lower()
    club = ClubInfo.objects.first()
    club_key = club.name.strip().lower() if club else "gurkhali fc"

    group_ids = set(
        GroupTeam.objects.filter(name__iexact=match.opponent).values_list(
            "group_id", flat=True
        )
    )
    group_ids.update(
        GroupTeam.objects.filter(is_club=True).values_list("group_id", flat=True)
    )
    if club:
        group_ids.update(
            GroupTeam.objects.filter(name__iexact=club.name).values_list(
                "group_id", flat=True
            )
        )

    # Always refresh groups that contain the opponent or the club side.
    # If the opponent isn't in any group, still refresh club groups so a
    # removed/renamed opponent doesn't leave stale points behind.
    if not group_ids and opponent_key:
        group_ids.update(
            GroupTeam.objects.filter(name__iexact=club_key).values_list(
                "group_id", flat=True
            )
        )

    for group in CompetitionGroup.objects.filter(pk__in=group_ids).prefetch_related(
        "teams"
    ):
        recalculate_group_standings(group)

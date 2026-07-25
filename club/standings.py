"""Sync World Cup group tables from finished two-team Match scores.

A Match is home_team vs away_team. When Finished with both scores set, any
CompetitionGroup that contains both team names (or the match.group FK) is
recalculated from all finished results in that group.
"""

from .models import CompetitionGroup, GroupTeam, Match


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


def _match_counts_for_group(match, group, by_name):
    if match.group_id == group.pk:
        return True
    home = by_name.get(match.home_team.strip().lower())
    away = by_name.get(match.away_team.strip().lower())
    return home is not None and away is not None


def recalculate_group_standings(group):
    """Reset a group's team stats and rebuild them from finished matches."""
    teams = list(group.teams.all())
    if not teams:
        return

    by_name = {team.name.strip().lower(): team for team in teams}
    stats = {team.pk: _empty_stats() for team in teams}

    finished_matches = Match.objects.filter(
        status=Match.Status.FINISHED,
        home_score__isnull=False,
        away_score__isnull=False,
    )

    for match in finished_matches:
        if not _match_counts_for_group(match, group, by_name):
            continue
        home = by_name.get(match.home_team.strip().lower())
        away = by_name.get(match.away_team.strip().lower())
        if home is None or away is None:
            continue
        _apply_result(stats[home.pk], match.home_score, match.away_score)
        _apply_result(stats[away.pk], match.away_score, match.home_score)

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
    """Recalculate every group affected by this home vs away fixture."""
    group_ids = set()

    if match.group_id:
        group_ids.add(match.group_id)

    home = (match.home_team or "").strip()
    away = (match.away_team or "").strip()
    if home and away:
        home_groups = set(
            GroupTeam.objects.filter(name__iexact=home).values_list(
                "group_id", flat=True
            )
        )
        away_groups = set(
            GroupTeam.objects.filter(name__iexact=away).values_list(
                "group_id", flat=True
            )
        )
        group_ids.update(home_groups & away_groups)
        group_ids.update(home_groups)
        group_ids.update(away_groups)

    if not group_ids:
        return

    for group in CompetitionGroup.objects.filter(pk__in=group_ids).prefetch_related(
        "teams"
    ):
        recalculate_group_standings(group)

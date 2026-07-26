"""World Cup–style knockout bracket generation and advancement.

Progressive scheduling:
1. When the group stage finishes → schedule the first knockout round (QF/R16).
2. When that round is fully finished → schedule the next (SF, then Final).

With 4 active groups (top 2 advance → 8 teams): Quarter-finals →
Semi-finals → Final (+ optional third-place).

With 2 groups (top 2 → 4 teams): Semi-finals → Final.

With 8 groups (top 2 → 16 teams): Round of 16 → QF → SF → Final.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

from django.db.models import Q
from django.utils import timezone

from .models import ClubInfo, CompetitionGroup, Match

DEFAULT_DAYS_BETWEEN_ROUNDS = 3
DEFAULT_MATCH_TIME = datetime.time(18, 0)

# Avoid re-entrant progress while Match.save triggers generation/advance.
_PROGRESS_LOCK = False


@dataclass
class KnockoutResult:
    created: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    advanced: list = field(default_factory=list)


def group_letter(group):
    """Extract A/B/C… from names like 'Group A' or 'A'."""
    match = re.search(r"\b([A-H])\b", group.name.upper())
    if match:
        return match.group(1)
    # Fallback: first letter of the name.
    cleaned = re.sub(r"[^A-Za-z]", "", group.name)
    return cleaned[0].upper() if cleaned else "?"


def active_groups():
    return list(
        CompetitionGroup.objects.filter(is_active=True)
        .prefetch_related("teams")
        .order_by("name")
    )


def group_stage_progress(group):
    """Return (is_complete, finished_count, total_count) for a group's fixtures."""
    matches = Match.objects.filter(stage=Match.Stage.GROUP, group=group)
    total = matches.count()
    if total == 0:
        return False, 0, 0
    finished = matches.filter(status=Match.Status.FINISHED).count()
    return finished >= total, finished, total


def all_group_stages_complete(groups=None):
    groups = groups if groups is not None else active_groups()
    usable = [g for g in groups if g.teams.count() >= 2]
    if len(usable) < 2:
        return False
    return all(group_stage_progress(g)[0] for g in usable)


def qualifier_rows(groups=None):
    """Rows for the Knockout admin page: group, progress, 1st, 2nd.

    Team names stay hidden (TBD) until that group's stage is finished.
    """
    groups = groups if groups is not None else active_groups()
    rows = []
    for group in groups:
        complete, finished, total = group_stage_progress(group)
        standings = group.standings()
        letter = group_letter(group)
        if complete and len(standings) >= 2:
            first = standings[0]["team"].name
            second = standings[1]["team"].name
        elif complete and len(standings) >= 1:
            first = standings[0]["team"].name
            second = "—"
        else:
            first = "TBD"
            second = "TBD"
        rows.append(
            {
                "group": group,
                "letter": letter,
                "complete": complete,
                "finished": finished,
                "total": total,
                "first": first,
                "second": second,
                "seed_1": f"1{letter}",
                "seed_2": f"2{letter}",
            }
        )
    return rows


def planned_first_round_pairings(groups=None):
    """First-round knockout pairings.

    Seed codes always show. Real team names only appear once every
    group stage is finished — otherwise home/away stay as seeds (1A, 2B…).
    """
    groups = groups if groups is not None else active_groups()
    groups = [g for g in groups if g.teams.count() >= 2]
    letters = sorted({group_letter(g) for g in groups})
    if len(letters) < 2:
        return None, []
    stage, pair_codes = _pairing_plan(letters)
    reveal_teams = all_group_stages_complete(groups)
    qualifiers = qualifiers_from_groups(groups) if reveal_teams else {}
    pairings = []
    for home_code, away_code in pair_codes:
        pairings.append(
            {
                "home_seed": home_code,
                "away_seed": away_code,
                "home": qualifiers.get(home_code, home_code),
                "away": qualifiers.get(away_code, away_code),
                "teams_revealed": reveal_teams,
            }
        )
    return stage, pairings


def reset_knockout_fixtures():
    """Delete all knockout matches and clear the hub generated timestamp."""
    from .models import KnockoutBracket

    result = KnockoutResult()
    qs = Match.objects.exclude(stage=Match.Stage.GROUP)
    count = qs.count()
    qs.delete()
    KnockoutBracket.objects.update(generated_at=None)
    if count:
        result.advanced.append(f"Removed {count} knockout match(es).")
    else:
        result.skipped.append("No knockout fixtures to remove.")
    return result


def qualifiers_from_groups(groups):
    """Return { '1A': team, '2A': team, ... } from current standings."""
    qualifiers = {}
    for group in groups:
        letter = group_letter(group)
        standings = group.standings()
        if len(standings) < 2:
            continue
        qualifiers[f"1{letter}"] = standings[0]["team"].name
        qualifiers[f"2{letter}"] = standings[1]["team"].name
    return qualifiers


def _pairing_plan(letters):
    """FIFA-style crossover pairings for the first knockout round."""
    letters = sorted(letters)
    n = len(letters)
    if n == 2:
        a, b = letters
        return Match.Stage.SF, [
            (f"1{a}", f"2{b}"),
            (f"1{b}", f"2{a}"),
        ]
    if n == 4:
        a, b, c, d = letters
        return Match.Stage.QF, [
            (f"1{a}", f"2{b}"),
            (f"1{c}", f"2{d}"),
            (f"1{b}", f"2{a}"),
            (f"1{d}", f"2{c}"),
        ]
    if n == 8:
        # Standard WC R16 skeleton for groups A–H.
        return Match.Stage.R16, [
            ("1A", "2B"),
            ("1C", "2D"),
            ("1E", "2F"),
            ("1G", "2H"),
            ("1B", "2A"),
            ("1D", "2C"),
            ("1F", "2E"),
            ("1H", "2G"),
        ]
    # Generic: pair 1st of each with 2nd of the next.
    stage = Match.Stage.QF if n <= 4 else Match.Stage.R16
    pairs = []
    for i, letter in enumerate(letters):
        other = letters[(i + 1) % n]
        pairs.append((f"1{letter}", f"2{other}"))
    return stage, pairs


def _fixture_exists(stage, home, away, bracket_order=None):
    qs = Match.objects.filter(stage=stage).filter(
        Q(home_team__iexact=home, away_team__iexact=away)
        | Q(home_team__iexact=away, away_team__iexact=home)
    )
    if bracket_order is not None:
        qs = qs.filter(bracket_order=bracket_order)
    return qs.exists()


def _default_venue():
    club = ClubInfo.objects.first()
    return (club.home_ground if club and club.home_ground else "") or ""


def _hub_settings():
    """Pull scheduling defaults from the Knockout admin hub when present."""
    from .models import KnockoutBracket

    hub = KnockoutBracket.objects.filter(is_active=True).first() or (
        KnockoutBracket.objects.first()
    )
    return {
        "hub": hub,
        "start_date": hub.start_date if hub and hub.start_date else None,
        "include_third_place": hub.include_third_place if hub else True,
        "venue": _default_venue(),
    }


def generate_knockout_bracket(
    *,
    start_date=None,
    days_between_rounds=DEFAULT_DAYS_BETWEEN_ROUNDS,
    match_time=None,
    venue="",
    include_third_place=True,
    require_group_stage_complete=True,
):
    """Schedule only the first knockout round from finished group standings.

    Later rounds (SF / Final) are created when the previous round is fully
    finished — see ``advance_knockout_winners``.
    """
    result = KnockoutResult()
    groups = [g for g in active_groups() if g.teams.count() >= 2]
    if len(groups) < 2:
        result.errors.append(
            "Need at least 2 active groups with 2+ teams each to build a knockout."
        )
        return result

    if require_group_stage_complete and not all_group_stages_complete(groups):
        incomplete = [
            f"{g.name} ({group_stage_progress(g)[1]}/{group_stage_progress(g)[2]} finished)"
            for g in groups
            if not group_stage_progress(g)[0]
        ]
        result.errors.append(
            "Group stage is not finished yet. Finish all group matches first. "
            "Incomplete: " + "; ".join(incomplete)
        )
        return result

    qualifiers = qualifiers_from_groups(groups)
    letters = sorted({group_letter(g) for g in groups})
    first_stage, pair_codes = _pairing_plan(letters)

    missing = [code for pair in pair_codes for code in pair if code not in qualifiers]
    if missing:
        result.errors.append(
            "Not enough group standings to fill the bracket. Make sure each "
            f"group has at least 2 teams. Missing seeds: {', '.join(sorted(set(missing)))}."
        )
        return result

    if start_date is None:
        start_date = timezone.localdate() + datetime.timedelta(days=7)
    if match_time is None:
        match_time = DEFAULT_MATCH_TIME
    if not venue:
        venue = _default_venue()

    for index, (home_code, away_code) in enumerate(pair_codes, start=1):
        home = qualifiers[home_code]
        away = qualifiers[away_code]
        existing = Match.objects.filter(stage=first_stage, bracket_order=index).first()
        if existing:
            # Upgrade leftover placeholder shells to real qualifier teams.
            changed = False
            if _is_placeholder(existing.home_team):
                existing.home_team = home
                changed = True
            if _is_placeholder(existing.away_team):
                existing.away_team = away
                changed = True
            if changed:
                if not existing.match_date:
                    existing.match_date = start_date
                if not existing.match_time:
                    existing.match_time = match_time
                if not existing.venue:
                    existing.venue = venue
                existing.notes = f"Knockout: {home_code} vs {away_code}"
                existing.save()
                result.advanced.append(
                    f"{first_stage} #{index}: {existing.home_team} vs {existing.away_team}"
                )
            else:
                result.skipped.append(f"{first_stage} #{index}: {home} vs {away}")
            continue

        if _fixture_exists(first_stage, home, away, bracket_order=index):
            result.skipped.append(f"{first_stage} #{index}: {home} vs {away}")
            continue

        match = Match.objects.create(
            home_team=home,
            away_team=away,
            stage=first_stage,
            bracket_order=index,
            match_date=start_date,
            match_time=match_time,
            venue=venue,
            status=Match.Status.SCHEDULED,
            notes=f"Knockout: {home_code} vs {away_code}",
        )
        result.created.append(match)

    return result


def _round_matches(stage):
    return list(Match.objects.filter(stage=stage).order_by("bracket_order", "pk"))


def _round_fully_decided(matches):
    return bool(matches) and all(
        m.status == Match.Status.FINISHED and m.winner for m in matches
    )


def _loser_of(match):
    if not match.winner:
        return None
    if match.winner == match.home_team:
        return match.away_team
    if match.winner == match.away_team:
        return match.home_team
    return None


def _schedule_or_fill_tie(
    *,
    stage,
    bracket_order,
    home,
    away,
    match_date,
    match_time,
    venue,
    notes,
    result,
):
    """Create a scheduled knockout tie, or fill an existing placeholder."""
    existing = Match.objects.filter(stage=stage, bracket_order=bracket_order).first()
    if existing:
        if existing.status == Match.Status.FINISHED:
            result.skipped.append(f"{stage} #{bracket_order} already finished")
            return existing

        changed = False
        if _is_placeholder(existing.home_team) or existing.home_team != home:
            existing.home_team = home
            changed = True
        if _is_placeholder(existing.away_team) or existing.away_team != away:
            existing.away_team = away
            changed = True
        if existing.match_date != match_date:
            existing.match_date = match_date
            changed = True
        if match_time and existing.match_time != match_time:
            existing.match_time = match_time
            changed = True
        if venue and not existing.venue:
            existing.venue = venue
            changed = True
        if existing.status != Match.Status.SCHEDULED:
            existing.status = Match.Status.SCHEDULED
            changed = True
        if changed:
            if notes:
                existing.notes = notes
            existing.save()
            result.advanced.append(
                f"{stage} #{bracket_order}: {existing.home_team} vs {existing.away_team}"
            )
        else:
            result.skipped.append(f"{stage} #{bracket_order} already set")
        return existing

    match = Match.objects.create(
        home_team=home,
        away_team=away,
        stage=stage,
        bracket_order=bracket_order,
        match_date=match_date,
        match_time=match_time,
        venue=venue,
        status=Match.Status.SCHEDULED,
        notes=notes,
    )
    result.created.append(match)
    result.advanced.append(f"{stage} #{bracket_order}: {home} vs {away}")
    return match


def advance_knockout_winners(
    *,
    days_between_rounds=DEFAULT_DAYS_BETWEEN_ROUNDS,
    match_time=None,
    venue="",
    include_third_place=None,
):
    """When a knockout round is fully finished, schedule the next round.

    Example: all Quarter-finals Finished with winners → create/fill Semi-finals
    with real teams and a new match date. Same for SF → Final (+ 3rd place).
    """
    result = KnockoutResult()
    settings = _hub_settings()
    if match_time is None:
        match_time = DEFAULT_MATCH_TIME
    if not venue:
        venue = settings["venue"]
    if include_third_place is None:
        include_third_place = settings["include_third_place"]

    stage_flow = [
        (Match.Stage.R16, Match.Stage.QF),
        (Match.Stage.QF, Match.Stage.SF),
        (Match.Stage.SF, Match.Stage.FINAL),
    ]

    for from_stage, to_stage in stage_flow:
        prior = _round_matches(from_stage)
        if not _round_fully_decided(prior):
            continue

        winners = [m.winner for m in prior]
        if len(winners) < 2:
            continue

        next_date = max(m.match_date for m in prior) + datetime.timedelta(
            days=days_between_rounds
        )
        next_count = len(winners) // 2

        for index in range(1, next_count + 1):
            home = winners[index * 2 - 2]
            away = winners[index * 2 - 1]
            _schedule_or_fill_tie(
                stage=to_stage,
                bracket_order=index,
                home=home,
                away=away,
                match_date=next_date,
                match_time=match_time,
                venue=venue,
                notes=f"Auto-scheduled from {from_stage} winners",
                result=result,
            )

        if from_stage == Match.Stage.SF and include_third_place:
            losers = [_loser_of(m) for m in prior[:2]]
            if all(losers):
                _schedule_or_fill_tie(
                    stage=Match.Stage.THIRD,
                    bracket_order=1,
                    home=losers[0],
                    away=losers[1],
                    match_date=next_date,
                    match_time=match_time,
                    venue=venue,
                    notes="Auto-scheduled 3rd-place play-off from SF losers",
                    result=result,
                )

    if not result.advanced and not result.created and not result.errors:
        result.errors.append(
            "Nothing to advance — finish every match in the current knockout "
            "round first (all QF before SF, all SF before Final)."
        )
    return result


def maybe_progress_knockout(match, previous_status=None):
    """Auto-schedule QF after groups, then SF/Final after each round ends.

    Called from Match.save when a fixture becomes Finished.
    """
    global _PROGRESS_LOCK
    if _PROGRESS_LOCK:
        return None
    if match.status != Match.Status.FINISHED:
        return None
    if previous_status == Match.Status.FINISHED:
        return None

    result = KnockoutResult()
    _PROGRESS_LOCK = True
    try:
        if match.stage == Match.Stage.GROUP and all_group_stages_complete():
            settings = _hub_settings()
            planned_stage, _pairings = planned_first_round_pairings()
            if planned_stage:
                knockout_qs = Match.objects.exclude(stage=Match.Stage.GROUP)
                has_opening = Match.objects.filter(stage=planned_stage).exists()
                # If an older/smaller bracket was built (e.g. SF while we now
                # need QF), clear it so the correct first round can schedule.
                if knockout_qs.exists() and not has_opening:
                    reset_knockout_fixtures()

            generated = generate_knockout_bracket(
                start_date=settings["start_date"],
                include_third_place=settings["include_third_place"],
                venue=settings["venue"],
                require_group_stage_complete=True,
            )
            result.created.extend(generated.created)
            result.advanced.extend(generated.advanced)
            result.errors.extend(generated.errors)
            hub = settings["hub"]
            if hub and (generated.created or generated.advanced):
                hub.generated_at = timezone.now()
                hub.save(update_fields=["generated_at"])

        if match.stage != Match.Stage.GROUP:
            settings = _hub_settings()
            advanced = advance_knockout_winners(
                include_third_place=settings["include_third_place"],
                venue=settings["venue"],
            )
            result.created.extend(advanced.created)
            result.advanced.extend(advanced.advanced)
            # Ignore the benign "nothing to advance" notice during auto-progress.
            for error in advanced.errors:
                if error.startswith("Nothing to advance"):
                    continue
                result.errors.append(error)
    finally:
        _PROGRESS_LOCK = False

    return result


def _is_placeholder(name):
    name = (name or "").strip()
    return name.startswith("Winner ") or name.startswith("Loser ")

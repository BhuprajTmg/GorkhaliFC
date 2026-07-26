"""World Cup–style knockout bracket generation and advancement.

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


def generate_knockout_bracket(
    *,
    start_date=None,
    days_between_rounds=3,
    match_time=None,
    venue="",
    include_third_place=True,
    require_group_stage_complete=True,
):
    """Create the first knockout round from active group standings.

    Also creates empty placeholder shells for later rounds (Winner QF1, etc.)
    so the bracket structure exists in admin.
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
        match_time = datetime.time(18, 0)
    if not venue:
        club = ClubInfo.objects.first()
        venue = (club.home_ground if club and club.home_ground else "") or ""

    # --- First knockout round (real team names from standings) ---
    first_round_matches = []
    for index, (home_code, away_code) in enumerate(pair_codes, start=1):
        home = qualifiers[home_code]
        away = qualifiers[away_code]
        if _fixture_exists(first_stage, home, away, bracket_order=index):
            result.skipped.append(f"{first_stage} #{index}: {home} vs {away}")
            existing = Match.objects.filter(
                stage=first_stage, bracket_order=index
            ).first()
            if existing:
                first_round_matches.append(existing)
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
        first_round_matches.append(match)

    # --- Later rounds as Winner placeholders ---
    round_chain = _later_rounds(first_stage, len(pair_codes), include_third_place)
    previous_count = len(pair_codes)
    previous_label = first_stage
    round_date = start_date

    for stage, count, use_winners_of in round_chain:
        round_date = round_date + datetime.timedelta(days=days_between_rounds)
        for index in range(1, count + 1):
            if stage == Match.Stage.THIRD:
                home = f"Loser {use_winners_of}1"
                away = f"Loser {use_winners_of}2"
            elif use_winners_of:
                home = f"Winner {use_winners_of}{index * 2 - 1}"
                away = f"Winner {use_winners_of}{index * 2}"
            else:
                home = f"Winner {previous_label}{index * 2 - 1}"
                away = f"Winner {previous_label}{index * 2}"

            if Match.objects.filter(stage=stage, bracket_order=index).exists():
                result.skipped.append(f"{stage} #{index}")
                continue

            match = Match.objects.create(
                home_team=home,
                away_team=away,
                stage=stage,
                bracket_order=index,
                match_date=round_date,
                match_time=match_time,
                venue=venue,
                status=Match.Status.SCHEDULED,
                notes=f"Knockout placeholder — run 'Advance knockout winners' after prior round.",
            )
            result.created.append(match)

        previous_count = count
        previous_label = stage

    return result


def _later_rounds(first_stage, first_count, include_third_place):
    """Return [(stage, match_count, winners_label), ...] after the first round."""
    chain = []
    stage = first_stage
    count = first_count

    order = [
        Match.Stage.R16,
        Match.Stage.QF,
        Match.Stage.SF,
        Match.Stage.FINAL,
    ]
    try:
        start_idx = order.index(stage)
    except ValueError:
        start_idx = 0

    prev = stage
    for next_stage in order[start_idx + 1 :]:
        if next_stage == Match.Stage.FINAL:
            chain.append((Match.Stage.FINAL, 1, prev))
            if include_third_place and prev == Match.Stage.SF:
                chain.append((Match.Stage.THIRD, 1, prev))
            break
        next_count = max(1, count // 2)
        chain.append((next_stage, next_count, prev))
        prev = next_stage
        count = next_count
    return chain


def advance_knockout_winners():
    """Fill next-round placeholders from finished knockout results."""
    result = KnockoutResult()
    stage_flow = [
        (Match.Stage.R16, Match.Stage.QF),
        (Match.Stage.QF, Match.Stage.SF),
        (Match.Stage.SF, Match.Stage.FINAL),
    ]

    for from_stage, to_stage in stage_flow:
        finished = list(
            Match.objects.filter(
                stage=from_stage, status=Match.Status.FINISHED
            ).order_by("bracket_order")
        )
        if not finished:
            continue

        next_matches = list(
            Match.objects.filter(stage=to_stage).order_by("bracket_order")
        )
        for next_match in next_matches:
            # Map QF1+QF2 → SF1, QF3+QF4 → SF2, etc.
            left_order = next_match.bracket_order * 2 - 1
            right_order = next_match.bracket_order * 2
            left = next((m for m in finished if m.bracket_order == left_order), None)
            right = next((m for m in finished if m.bracket_order == right_order), None)
            if not left or not right:
                continue
            left_winner = left.winner
            right_winner = right.winner
            if not left_winner or not right_winner:
                result.errors.append(
                    f"Cannot advance to {to_stage} #{next_match.bracket_order}: "
                    "a prior match is drawn or unfinished (set a winner)."
                )
                continue

            changed = False
            # Only overwrite placeholder slots so manual edits are kept.
            if _is_placeholder(next_match.home_team):
                next_match.home_team = left_winner
                changed = True
            if _is_placeholder(next_match.away_team):
                next_match.away_team = right_winner
                changed = True

            if changed:
                next_match.save()
                result.advanced.append(
                    f"{to_stage} #{next_match.bracket_order}: "
                    f"{next_match.home_team} vs {next_match.away_team}"
                )

        # Third place from SF losers
        if from_stage == Match.Stage.SF:
            third = Match.objects.filter(
                stage=Match.Stage.THIRD, bracket_order=1
            ).first()
            if third and len(finished) >= 2:
                losers = []
                for m in finished[:2]:
                    if m.winner == m.home_team:
                        losers.append(m.away_team)
                    elif m.winner == m.away_team:
                        losers.append(m.home_team)
                if len(losers) == 2 and (
                    _is_placeholder(third.home_team)
                    or third.home_team.startswith("Loser ")
                ):
                    third.home_team = losers[0]
                    third.away_team = losers[1]
                    third.save()
                    result.advanced.append(
                        f"THIRD: {third.home_team} vs {third.away_team}"
                    )

    if not result.advanced and not result.errors:
        result.errors.append(
            "Nothing to advance — finish knockout matches first, or generate the bracket."
        )
    return result


def _is_placeholder(name):
    name = (name or "").strip()
    return name.startswith("Winner ") or name.startswith("Loser ")

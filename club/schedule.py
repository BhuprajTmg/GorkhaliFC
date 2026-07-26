"""Match schedule display rules for the public site.

- Show Live matches immediately.
- Show the next 5 Scheduled group-stage fixtures (Next + Upcoming).
- Show a visual knockout bracket (QF / SF / Final) in the schedule hero.
- Finished group matches remain visible for FINISHED_VISIBLE_MINUTES, then drop off.
"""

from datetime import timedelta

from django.utils import timezone

from .models import Match

UPCOMING_LIMIT = 5
FINISHED_VISIBLE_MINUTES = 5

KNOCKOUT_STAGE_ORDER = [
    Match.Stage.R16,
    Match.Stage.QF,
    Match.Stage.SF,
    Match.Stage.THIRD,
    Match.Stage.FINAL,
]

# Visual bracket columns (left → right). Third-place sits under the Final.
BRACKET_DISPLAY_STAGES = [
    Match.Stage.R16,
    Match.Stage.QF,
    Match.Stage.SF,
    Match.Stage.FINAL,
]

BRACKET_SHORT = {
    Match.Stage.R16: "R16",
    Match.Stage.QF: "QF",
    Match.Stage.SF: "SF",
    Match.Stage.THIRD: "3rd",
    Match.Stage.FINAL: "Final",
}

PLACEHOLDER_COUNTS = {
    Match.Stage.R16: 8,
    Match.Stage.QF: 4,
    Match.Stage.SF: 2,
    Match.Stage.THIRD: 1,
    Match.Stage.FINAL: 1,
}


def _slot_from_match(match):
    home_wins = (
        match.status == Match.Status.FINISHED
        and match.home_score is not None
        and match.away_score is not None
        and match.home_score > match.away_score
    )
    away_wins = (
        match.status == Match.Status.FINISHED
        and match.home_score is not None
        and match.away_score is not None
        and match.away_score > match.home_score
    )
    return {
        "match": match,
        "home": match.home_team,
        "away": match.away_team,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "home_wins": home_wins,
        "away_wins": away_wins,
        "status": match.status,
        "is_live": match.is_live,
        "is_finished": match.status == Match.Status.FINISHED,
        "is_placeholder": False,
        "match_date": match.match_date,
        "match_time": match.match_time,
        "venue": match.venue,
        "notes": match.notes,
        "stage_badge": match.stage_badge,
        "stage_label": match.get_stage_display(),
    }


def _placeholder_slot(home="TBD", away="TBD", badge="", stage_label=""):
    return {
        "match": None,
        "home": home,
        "away": away,
        "home_score": None,
        "away_score": None,
        "home_wins": False,
        "away_wins": False,
        "status": Match.Status.SCHEDULED,
        "is_live": False,
        "is_finished": False,
        "is_placeholder": True,
        "match_date": None,
        "match_time": None,
        "venue": "",
        "notes": "",
        "stage_badge": badge,
        "stage_label": stage_label or badge,
    }


def _slots_for_stage(stage, matches_by_stage, planned_pairings=None):
    """Build display slots for one knockout stage (real fixtures or placeholders)."""
    matches = matches_by_stage.get(stage, [])
    badge = BRACKET_SHORT.get(stage, stage)
    if matches:
        return [_slot_from_match(m) for m in matches]

    stage_label = dict(Match.Stage.choices).get(stage, badge)

    # First knockout round can preview from current group-table standings.
    if planned_pairings and stage in (Match.Stage.R16, Match.Stage.QF, Match.Stage.SF):
        return [
            _placeholder_slot(
                home=pair["home"],
                away=pair["away"],
                badge=badge,
                stage_label=stage_label,
            )
            for pair in planned_pairings
        ]

    count = PLACEHOLDER_COUNTS.get(stage, 1)
    if stage == Match.Stage.SF:
        labels = [
            ("Winner QF 1", "Winner QF 2"),
            ("Winner QF 3", "Winner QF 4"),
        ][:count]
        return [
            _placeholder_slot(h, a, badge, stage_label=stage_label) for h, a in labels
        ]
    if stage == Match.Stage.FINAL:
        return [
            _placeholder_slot(
                "Winner SF 1", "Winner SF 2", badge, stage_label=stage_label
            )
        ]
    if stage == Match.Stage.THIRD:
        return [
            _placeholder_slot(
                "Loser SF 1", "Loser SF 2", badge, stage_label=stage_label
            )
        ]
    if stage == Match.Stage.R16:
        return [
            _placeholder_slot(
                f"1{chr(65 + i)}",
                f"2{chr(65 + i)}",
                badge,
                stage_label=stage_label,
            )
            for i in range(count)
        ]
    return [
        _placeholder_slot(
            f"Qualifier {i * 2 + 1}",
            f"Qualifier {i * 2 + 2}",
            badge,
            stage_label=stage_label,
        )
        for i in range(count)
    ]


def build_knockout_bracket_display():
    """Structured QF → SF → Final tree for the public knockout UI.

    Uses real knockout fixtures when present. Otherwise previews the first
    round from current group standings and shows TBD slots for later rounds.
    """
    from .knockout import all_group_stages_complete, planned_first_round_pairings

    matches_by_stage = {}
    for stage in KNOCKOUT_STAGE_ORDER:
        matches_by_stage[stage] = list(
            Match.objects.filter(stage=stage).order_by(
                "bracket_order", "match_date", "match_time", "pk"
            )
        )

    has_fixtures = any(matches_by_stage[s] for s in KNOCKOUT_STAGE_ORDER)
    planned_stage, planned_pairings = planned_first_round_pairings()

    earliest_fixture_stage = None
    for stage in (Match.Stage.R16, Match.Stage.QF, Match.Stage.SF, Match.Stage.FINAL):
        if matches_by_stage[stage]:
            earliest_fixture_stage = stage
            break

    opening_stage = (
        earliest_fixture_stage
        if earliest_fixture_stage and earliest_fixture_stage != Match.Stage.FINAL
        else (planned_stage or Match.Stage.QF)
    )
    if earliest_fixture_stage == Match.Stage.FINAL and not (
        matches_by_stage[Match.Stage.R16]
        or matches_by_stage[Match.Stage.QF]
        or matches_by_stage[Match.Stage.SF]
    ):
        # Final-only data: still show SF placeholders feeding the Final.
        opening_stage = Match.Stage.SF

    columns = []
    for stage in BRACKET_DISPLAY_STAGES:
        stage_matches = matches_by_stage.get(stage, [])
        # Skip empty early rounds that don't apply (e.g. no R16 with 4 groups).
        if (
            stage != Match.Stage.FINAL
            and not stage_matches
            and opening_stage
            and _stage_rank(stage) < _stage_rank(opening_stage)
        ):
            continue

        use_pairings = (
            not has_fixtures
            and planned_pairings
            and stage == opening_stage
        )
        if stage_matches:
            slots = _slots_for_stage(stage, matches_by_stage)
        elif use_pairings:
            slots = _slots_for_stage(
                stage, matches_by_stage, planned_pairings=planned_pairings
            )
        else:
            # Later rounds without fixtures: elegant TBD placeholders.
            slots = _slots_for_stage(stage, {}, planned_pairings=None)

        live_count = sum(1 for s in slots if s.get("is_live"))
        done_count = sum(1 for s in slots if s.get("is_finished"))
        columns.append(
            {
                "stage": stage,
                "label": dict(Match.Stage.choices).get(stage, stage),
                "short": BRACKET_SHORT.get(stage, stage),
                "panel_id": f"knockout-panel-{stage.lower()}",
                "slots": slots,
                "match_count": len(slots),
                "live_count": live_count,
                "done_count": done_count,
                "is_final": stage == Match.Stage.FINAL,
            }
        )

    third_slots = _slots_for_stage(
        Match.Stage.THIRD,
        matches_by_stage,
        planned_pairings=None,
    )
    # Only surface third-place when a fixture exists or finals are already live.
    show_third = bool(matches_by_stage.get(Match.Stage.THIRD)) or bool(
        matches_by_stage.get(Match.Stage.FINAL)
    )

    return {
        "has_fixtures": has_fixtures,
        "group_stage_complete": all_group_stages_complete(),
        "columns": columns,
        "third": third_slots[0] if show_third and third_slots else None,
        "opening_stage": opening_stage,
    }


def _stage_rank(stage):
    order = {
        Match.Stage.R16: 0,
        Match.Stage.QF: 1,
        Match.Stage.SF: 2,
        Match.Stage.THIRD: 3,
        Match.Stage.FINAL: 4,
    }
    return order.get(stage, 99)


def build_match_schedule(now=None):
    """Return live, next, upcoming, knockout, and recently-finished lists."""
    now = now or timezone.now()

    live_matches = list(
        Match.objects.filter(status=Match.Status.LIVE).order_by(
            "match_date", "match_time", "pk"
        )
    )

    scheduled_group = list(
        Match.objects.filter(
            status=Match.Status.SCHEDULED,
            stage=Match.Stage.GROUP,
        ).order_by("match_date", "match_time", "pk")[:UPCOMING_LIMIT]
    )
    next_match = scheduled_group[0] if scheduled_group else None
    upcoming_matches = scheduled_group[1:] if next_match else []

    # Flat knockout lists kept for tests / secondary use; public UI uses
    # the visual bracket from build_knockout_bracket_display().
    knockout_rounds = []
    for stage in KNOCKOUT_STAGE_ORDER:
        matches = list(
            Match.objects.filter(stage=stage)
            .exclude(status=Match.Status.FINISHED)
            .order_by("bracket_order", "match_date", "match_time", "pk")
        )
        cutoff = now - timedelta(minutes=FINISHED_VISIBLE_MINUTES)
        recent_finished = list(
            Match.objects.filter(
                stage=stage,
                status=Match.Status.FINISHED,
                finished_at__gte=cutoff,
            ).order_by("bracket_order", "-finished_at")
        )
        combined = matches + [m for m in recent_finished if m not in matches]
        if combined:
            knockout_rounds.append(
                {
                    "stage": stage,
                    "label": dict(Match.Stage.choices).get(stage, stage),
                    "matches": combined,
                }
            )

    cutoff = now - timedelta(minutes=FINISHED_VISIBLE_MINUTES)
    past_matches = list(
        Match.objects.filter(
            status=Match.Status.FINISHED,
            stage=Match.Stage.GROUP,
            finished_at__gte=cutoff,
        ).order_by("-finished_at", "-match_date", "-match_time")
    )

    return {
        "live_matches": live_matches,
        "next_match": next_match,
        "upcoming_matches": upcoming_matches,
        "knockout_rounds": knockout_rounds,
        "knockout_bracket": build_knockout_bracket_display(),
        "past_matches": past_matches,
        "finished_visible_minutes": FINISHED_VISIBLE_MINUTES,
    }

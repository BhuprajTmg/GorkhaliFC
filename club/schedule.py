"""Match schedule display rules for the public site.

- Show Live matches immediately.
- Show the next 5 Scheduled group-stage fixtures (Next + Upcoming).
- Show knockout rounds (R16 / QF / SF / Final) in their own section.
- Finished matches remain visible for FINISHED_VISIBLE_MINUTES, then drop off.
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

    knockout_rounds = []
    for stage in KNOCKOUT_STAGE_ORDER:
        matches = list(
            Match.objects.filter(stage=stage)
            .exclude(status=Match.Status.FINISHED)
            .order_by("bracket_order", "match_date", "match_time", "pk")
        )
        # Also show recently finished knockout ties briefly.
        cutoff = now - timedelta(minutes=FINISHED_VISIBLE_MINUTES)
        recent_finished = list(
            Match.objects.filter(
                stage=stage,
                status=Match.Status.FINISHED,
                finished_at__gte=cutoff,
            ).order_by("bracket_order", "-finished_at")
        )
        combined = matches + [
            m for m in recent_finished if m not in matches
        ]
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
        "past_matches": past_matches,
        "finished_visible_minutes": FINISHED_VISIBLE_MINUTES,
    }

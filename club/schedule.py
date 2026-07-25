"""Match schedule display rules for the public site.

- Show Live matches immediately.
- Show the next 5 Scheduled fixtures (first as Next Match, rest as Upcoming).
- Finished matches remain visible for FINISHED_VISIBLE_MINUTES, then drop off.
"""

from datetime import timedelta

from django.utils import timezone

from .models import Match

UPCOMING_LIMIT = 5
FINISHED_VISIBLE_MINUTES = 5


def build_match_schedule(now=None):
    """Return live, next, upcoming, and recently-finished match lists."""
    now = now or timezone.now()

    live_matches = list(
        Match.objects.filter(status=Match.Status.LIVE).order_by(
            "match_date", "match_time", "pk"
        )
    )

    scheduled = list(
        Match.objects.filter(status=Match.Status.SCHEDULED).order_by(
            "match_date", "match_time", "pk"
        )[:UPCOMING_LIMIT]
    )
    next_match = scheduled[0] if scheduled else None
    upcoming_matches = scheduled[1:] if next_match else []

    cutoff = now - timedelta(minutes=FINISHED_VISIBLE_MINUTES)
    past_matches = list(
        Match.objects.filter(
            status=Match.Status.FINISHED,
            finished_at__gte=cutoff,
        ).order_by("-finished_at", "-match_date", "-match_time")
    )

    return {
        "live_matches": live_matches,
        "next_match": next_match,
        "upcoming_matches": upcoming_matches,
        "past_matches": past_matches,
        "finished_visible_minutes": FINISHED_VISIBLE_MINUTES,
    }

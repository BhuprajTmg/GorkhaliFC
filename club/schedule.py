"""Match schedule display rules for the public site.

Only one fixture is revealed at a time as "Next Match". The queue advances
strictly when every chronologically earlier match has status FINISHED.
While a match is LIVE, the Next Match slot stays empty. Later scheduled
fixtures are not listed under Upcoming until they become the queue head.
"""

from .models import Match


def build_match_schedule():
    """Return live, next, upcoming, and past match lists for the homepage.

    upcoming is always empty under the current reveal rules — kept in the
    return signature so the template/section can stay in place if the club
    later wants a controlled preview list.
    """
    ordered = list(
        Match.objects.order_by("match_date", "match_time", "pk")
    )
    live_matches = [m for m in ordered if m.status == Match.Status.LIVE]
    past_matches = [
        m for m in reversed(ordered) if m.status == Match.Status.FINISHED
    ]

    next_match = None
    for match in ordered:
        if match.status == Match.Status.FINISHED:
            continue
        # First non-finished match controls the schedule pointer.
        if match.status == Match.Status.LIVE:
            # Still in progress — do not promote the following fixture yet.
            break
        if match.status == Match.Status.SCHEDULED:
            next_match = match
        break

    return {
        "live_matches": live_matches,
        "next_match": next_match,
        "upcoming_matches": [],
        "past_matches": past_matches,
    }

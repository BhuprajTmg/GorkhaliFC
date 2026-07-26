"""Template context shared across public pages."""

from .models import CompetitionGroup, GroupTeam


def schedule_nav(request):
    """Expose whether the Match Schedule section should appear.

    Shown only once competition groups exist and teams have been placed
    into those groups (registered / drawn).
    """
    active_groups = CompetitionGroup.objects.filter(is_active=True)
    ready = active_groups.exists() and GroupTeam.objects.filter(
        group__in=active_groups
    ).exists()
    return {"schedule_ready": ready}

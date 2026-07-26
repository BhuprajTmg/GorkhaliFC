"""Side-effects for team registrations (emails on approval milestones)."""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import APPROVED_TEAMS_FOR_SCHEDULE, ClubInfo, TeamRegistration


@receiver(pre_save, sender=TeamRegistration)
def _remember_previous_registration_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    instance._previous_status = (
        TeamRegistration.objects.filter(pk=instance.pk)
        .values_list("status", flat=True)
        .first()
    )


@receiver(post_save, sender=TeamRegistration)
def _notify_when_all_teams_approved(sender, instance, **kwargs):
    """When the 16th team is approved, email every approved team about schedules."""
    previous = getattr(instance, "_previous_status", None)
    if instance.status != TeamRegistration.Status.APPROVED:
        return
    if previous == TeamRegistration.Status.APPROVED:
        return

    approved_count = TeamRegistration.objects.filter(
        status=TeamRegistration.Status.APPROVED
    ).count()
    if approved_count != APPROVED_TEAMS_FOR_SCHEDULE:
        return

    from .emails import send_schedule_ready_notifications

    send_schedule_ready_notifications(ClubInfo.objects.first())

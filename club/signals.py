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
def _on_registration_approved(sender, instance, created, **kwargs):
    """On transition to Approved: email that team (PDF), and if 16th, schedules."""
    previous = getattr(instance, "_previous_status", None)
    if instance.status != TeamRegistration.Status.APPROVED:
        return
    if previous == TeamRegistration.Status.APPROVED:
        return
    # Skip brand-new rows created already as Approved (e.g. seed_demo).
    # Email only when status is changed to Approved in admin.
    if created or previous is None:
        return

    from .emails import (
        send_registration_approved_confirmation,
        send_schedule_ready_notifications,
    )

    club = ClubInfo.objects.first()
    # One approval email to this team's Gmail, with PDF only.
    send_registration_approved_confirmation(instance, club)

    approved_count = TeamRegistration.objects.filter(
        status=TeamRegistration.Status.APPROVED
    ).count()
    if approved_count == APPROVED_TEAMS_FOR_SCHEDULE:
        send_schedule_ready_notifications(club)

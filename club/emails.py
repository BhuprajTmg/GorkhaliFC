"""Email notifications for the contact form and tournament registrations.

Uses Django's send_mail with fail_silently=True so a misconfigured or
temporarily unavailable mail server never breaks the site for visitors —
worst case, the submission is still saved to the database and visible in
the admin, and (in DEBUG, with no SMTP configured) the email is printed to
the console instead of actually being sent.
"""

from django.conf import settings
from django.core.mail import EmailMessage


def _notification_recipient(club):
    return (
        (club and club.email)
        or settings.CONTACT_NOTIFICATION_EMAIL
        or settings.DEFAULT_FROM_EMAIL
    )


def _send(subject, body, recipient, reply_to):
    if not recipient:
        return
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
        reply_to=[reply_to] if reply_to else None,
    )
    email.send(fail_silently=True)


def send_contact_notification(contact_message, club):
    _send(
        subject=f"[{club.name if club else 'Gurkhali FC'}] New contact message from {contact_message.name}",
        body=(
            f"You have a new message from the club website contact form.\n\n"
            f"Name: {contact_message.name}\n"
            f"Email: {contact_message.email}\n\n"
            f"Message:\n{contact_message.message}\n\n"
            f"Reply directly to {contact_message.email}, or view/manage this "
            f"message in the Django admin under Contact Messages."
        ),
        recipient=_notification_recipient(club),
        reply_to=contact_message.email,
    )


def send_registration_notification(registration, club):
    _send(
        subject=f"[{club.name if club else 'Gurkhali FC'}] New tournament registration: {registration.team_name}",
        body=(
            f"A new team has registered for a tournament via the club website.\n\n"
            f"Tournament: {registration.tournament_name}\n"
            f"Team name: {registration.team_name}\n"
            f"Division: {registration.get_division_display()}\n"
            f"Manager/coach: {registration.manager_name}\n"
            f"Phone: {registration.phone}\n"
            f"Email: {registration.email}\n"
            f"Estimated players: {registration.player_count}\n"
            f"Home city/suburb: {registration.home_city or '-'}\n"
            f"Previous tournament experience: {registration.experience or '-'}\n"
            f"Notes: {registration.notes or '-'}\n\n"
            f"Manage this registration (approve/reject) in the Django admin "
            f"under Team Registrations."
        ),
        recipient=_notification_recipient(club),
        reply_to=registration.email,
    )

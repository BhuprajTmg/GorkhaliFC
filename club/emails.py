"""Email notifications for the contact form and tournament registrations.

Sends via whatever EMAIL_BACKEND is configured (see settings.py) — SMTP if
EMAIL_HOST_USER/EMAIL_HOST_PASSWORD are set, otherwise the console backend,
which just prints the email to the terminal running `runserver` instead of
actually sending it (useful for local development without real credentials).

Failures are logged loudly (not swallowed) so a wrong password / SMTP block
/ etc. shows up clearly in the terminal instead of silently doing nothing —
but they never raise, so a broken mail server never breaks the page for the
visitor submitting the form; the submission is always saved to the database
and visible in the admin regardless of whether the email goes out.
"""

import io
import logging

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


def _notification_recipient(club):
    return (
        (club and club.email)
        or settings.CONTACT_NOTIFICATION_EMAIL
        or settings.DEFAULT_FROM_EMAIL
    )


def _send(subject, body, recipient, reply_to, attachments=None):
    if not recipient:
        message = (
            "Email not sent: no recipient configured. Set an email address "
            "on Club Info in the admin, or set CONTACT_NOTIFICATION_EMAIL."
        )
        logger.warning(message)
        print(f"[club.emails] {message}")
        return

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
        reply_to=[reply_to] if reply_to else None,
    )
    for filename, content, mimetype in attachments or []:
        email.attach(filename, content, mimetype)

    try:
        email.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 - we want to log *any* send failure
        message = (
            f"Failed to send email to {recipient} using "
            f"{settings.EMAIL_BACKEND} (host={settings.EMAIL_HOST}, "
            f"user={settings.EMAIL_HOST_USER or '(not set)'}): {exc!r}\n"
            "If you haven't already, add EMAIL_HOST_USER and "
            "EMAIL_HOST_PASSWORD to your .env file (see .env.example) and "
            "restart the server. For Gmail you need an App Password, not "
            "your normal password."
        )
        logger.error(message)
        print(f"[club.emails] {message}")
    else:
        print(f"[club.emails] Email sent to {recipient}: {subject}")


def build_registration_docx(registration, club):
    """Builds a Word (.docx) document summarising a tournament registration,
    returned as raw bytes ready to attach to an email.
    """
    from docx import Document
    from docx.shared import Pt

    document = Document()

    title = document.add_heading("Tournament Team Registration", level=1)
    title.runs[0].font.size = Pt(20)

    subtitle = document.add_paragraph()
    subtitle_run = subtitle.add_run(
        f"{club.name if club else 'Gurkhali FC'} — {registration.tournament_name}"
    )
    subtitle_run.bold = True
    subtitle_run.font.size = Pt(13)

    document.add_paragraph(
        f"Submitted: {registration.submitted_at.strftime('%d %B %Y, %I:%M %p')}"
    ).italic = True

    document.add_heading("Team Details", level=2)
    rows = [
        ("Tournament", registration.tournament_name),
        ("Team Name", registration.team_name),
        ("Division", registration.get_division_display()),
        ("Estimated Players", str(registration.player_count)),
        ("Home City / Suburb", registration.home_city or "-"),
        ("Status", registration.get_status_display()),
    ]
    _add_table(document, rows)

    document.add_heading("Contact", level=2)
    _add_table(
        document,
        [
            ("Manager / Coach", registration.manager_name),
            ("Phone", registration.phone),
            ("Email", registration.email),
        ],
    )

    document.add_heading("Additional Information", level=2)
    document.add_paragraph("Previous tournament experience:").bold = True
    document.add_paragraph(registration.experience or "None provided.")
    document.add_paragraph("Notes:").bold = True
    document.add_paragraph(registration.notes or "None provided.")

    document.add_paragraph()
    agreement = document.add_paragraph()
    agreement.add_run(
        "✔ Confirmed agreement to tournament rules and code of conduct."
        if registration.agreed_to_rules
        else "✘ Did NOT confirm agreement to tournament rules."
    ).bold = True

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _add_table(document, rows):
    table = document.add_table(rows=0, cols=2)
    table.style = "Light Grid Accent 1"
    for label, value in rows:
        row = table.add_row().cells
        row[0].text = label
        row[1].text = value
    return table


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
    docx_bytes = build_registration_docx(registration, club)
    safe_team_name = "".join(
        c for c in registration.team_name if c.isalnum() or c in (" ", "-", "_")
    ).strip() or "team"
    filename = f"Registration - {safe_team_name}.docx"

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
            f"A Word document with these details is attached. Manage this "
            f"registration (approve/reject) in the Django admin under Team "
            f"Registrations."
        ),
        recipient=_notification_recipient(club),
        reply_to=registration.email,
        attachments=[
            (
                filename,
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        ],
    )

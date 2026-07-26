"""Send a one-off test email to verify SMTP / Gmail App Password setup.

Usage:
  python manage.py send_test_email you@gmail.com
"""

from django.core.management.base import BaseCommand, CommandError

from club.emails import email_delivery_enabled, send_test_email
from club.models import ClubInfo


class Command(BaseCommand):
    help = "Send a test email to verify registration confirmation delivery."

    def add_arguments(self, parser):
        parser.add_argument(
            "to",
            nargs="?",
            help="Recipient address (defaults to Club Info email).",
        )

    def handle(self, *args, **options):
        club = ClubInfo.objects.first()
        to = (options.get("to") or (club.email if club else "") or "").strip()
        if not to:
            raise CommandError(
                "Provide a recipient: python manage.py send_test_email you@gmail.com "
                "(or set Club Info → Email in the admin)."
            )
        if not email_delivery_enabled():
            raise CommandError(
                "SMTP is not configured. Copy .env.example to .env, set "
                "EMAIL_HOST_USER to the club Gmail and EMAIL_HOST_PASSWORD to a "
                "Gmail App Password, then restart and try again."
            )
        if send_test_email(to, club):
            self.stdout.write(self.style.SUCCESS(f"Test email sent to {to}"))
        else:
            raise CommandError(
                f"Failed to send test email to {to}. Check the error printed above."
            )

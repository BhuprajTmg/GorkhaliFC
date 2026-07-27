"""Repair legacy DB artifacts that can make registration return HTTP 500.

Usage:
    python manage.py db_doctor

- Drops the stale `uniq_teamregistration_team_name_ci` expression index left
  behind by an earlier migration (SQLite rejects inserts against it in ways
  Django can't map to a form error).
- Removes duplicate team registrations, keeping the earliest per team name.
"""

from django.core.management.base import BaseCommand
from django.db import connection

from club.models import TeamRegistration

STALE_INDEX = "uniq_teamregistration_team_name_ci"


class Command(BaseCommand):
    help = "Fix duplicate registrations and stale unique indexes."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=%s",
                [STALE_INDEX],
            )
            found = cursor.fetchone()
            if found:
                cursor.execute(f'DROP INDEX IF EXISTS "{STALE_INDEX}"')
                self.stdout.write(
                    self.style.SUCCESS(f"Dropped stale index {STALE_INDEX}")
                )
            else:
                self.stdout.write(f"No stale index {STALE_INDEX} (good)")

        seen = {}
        removed = 0
        for reg in TeamRegistration.objects.order_by("submitted_at", "id"):
            key = (reg.team_name or "").strip().lower()
            if not key:
                continue
            if key in seen:
                self.stdout.write(f"Removing duplicate: {reg.team_name} (id={reg.pk})")
                reg.delete()
                removed += 1
            else:
                seen[key] = reg.pk

        if removed:
            self.stdout.write(
                self.style.SUCCESS(f"Removed {removed} duplicate registration(s)")
            )
        else:
            self.stdout.write("No duplicate registrations found")

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(seen)} unique team registration(s) remain. "
                "Now reload the web app."
            )
        )

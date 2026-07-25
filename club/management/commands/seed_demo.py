import datetime

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from club.models import (
    ClubInfo,
    CompetitionGroup,
    GalleryCategory,
    GroupTeam,
    Match,
    Player,
)


class Command(BaseCommand):
    help = (
        "Seeds club info, squad members and a placeholder fixture list based on "
        "the club's original static site, so the new Django site isn't empty on "
        "first run. Photos/bios/exact positions can be corrected later via the "
        "admin at /admin/."
    )

    def handle(self, *args, **options):
        club, created = ClubInfo.objects.get_or_create(
            name="Gurkhali FC",
            defaults={
                "tagline": "Himalayan Hearts, Top End Spirits",
                "location": "Darwin, Northern Territory, Australia",
                "about": (
                    "Gurkhali FC was founded in 2023 in Darwin, Northern Territory, "
                    "by a passionate group of Nepali-Australian footballers united "
                    "by their love for the beautiful game and their Himalayan "
                    "heritage.\n\n"
                    "Representing the Gorkhali spirit — courage, honour, and "
                    "brotherhood — we compete with pride on and off the pitch. Our "
                    "motto says it all: Himalayan Hearts, Top End Spirits.\n\n"
                    "We are more than a football club. We are a community, a "
                    "family, and a symbol of the strength that comes when cultures "
                    "unite under one badge."
                ),
                "founded_year": 2023,
                "home_ground": "Gardens Oval, Darwin",
                "email": "info@gurkhalifc.com.au",
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f"ClubInfo {'created' if created else 'already existed'}: {club.name}")
        )

        # Positions are best guesses for the players we don't have confirmed
        # roles for yet (Dinesh, Janak, Ranjan, Sudip) — correct these in the
        # admin once you have the real squad list.
        placeholder_players = [
            ("Sohan Khadka", Player.Position.GOALKEEPER, 1),
            ("Niroj Shrestha", Player.Position.DEFENDER, 4),
            ("Ujjwal Giri", Player.Position.DEFENDER, 5),
            ("Dinesh", Player.Position.MIDFIELDER, 8),
            ("Janak", Player.Position.MIDFIELDER, 10),
            ("Ranjan", Player.Position.FORWARD, 9),
            ("Sudip", Player.Position.FORWARD, 11),
        ]
        for index, (name, position, jersey) in enumerate(placeholder_players, start=1):
            player, created = Player.objects.get_or_create(
                slug=slugify(name),
                defaults={
                    "name": name,
                    "position": position,
                    "order": index,
                    "jersey_number": jersey,
                },
            )
            status = "created" if created else "already existed"
            self.stdout.write(f"Player {name}: {status}")

        for category_name in ["Matches", "Team Photos", "Training"]:
            category, created = GalleryCategory.objects.get_or_create(
                slug=slugify(category_name), defaults={"name": category_name}
            )
            status = "created" if created else "already existed"
            self.stdout.write(f"Gallery category {category_name}: {status}")

        today = datetime.date.today()
        placeholder_fixtures = [
            ("Darwin FC", 14, "Gardens Oval, Darwin", True, datetime.time(18, 0)),
            ("Casuarina SC", 21, "Casuarina Stadium", False, datetime.time(17, 30)),
            ("Palmerston FC", 28, "Gardens Oval, Darwin", True, datetime.time(19, 0)),
            ("Nightcliff FC", 42, "Nightcliff Oval", False, datetime.time(16, 0)),
        ]
        for opponent, days_ahead, venue, is_home, match_time in placeholder_fixtures:
            match_date = today + datetime.timedelta(days=days_ahead)
            match, created = Match.objects.get_or_create(
                opponent=opponent,
                match_date=match_date,
                defaults={
                    "venue": venue,
                    "is_home": is_home,
                    "match_time": match_time,
                },
            )
            status = "created" if created else "already existed"
            self.stdout.write(f"Fixture vs {opponent}: {status}")

        # World Cup–format group of four (standings editable in admin).
        group, group_created = CompetitionGroup.objects.get_or_create(
            name="Group A",
            defaults={
                "season": "Darwin Cup 2026",
                "is_active": True,
            },
        )
        self.stdout.write(
            f"Competition group {group.name}: "
            f"{'created' if group_created else 'already existed'}"
        )
        group_teams = [
            # name, is_club, P, W, D, L, GF, GA
            ("Gurkhali FC", True, 3, 2, 1, 0, 7, 2),
            ("Darwin FC", False, 3, 2, 0, 1, 5, 3),
            ("Casuarina SC", False, 3, 1, 0, 2, 3, 5),
            ("Palmerston FC", False, 3, 0, 1, 2, 2, 7),
        ]
        for name, is_club, played, won, drawn, lost, gf, ga in group_teams:
            team, created = GroupTeam.objects.get_or_create(
                group=group,
                name=name,
                defaults={
                    "is_club": is_club,
                    "played": played,
                    "won": won,
                    "drawn": drawn,
                    "lost": lost,
                    "goals_for": gf,
                    "goals_against": ga,
                },
            )
            status = "created" if created else "already existed"
            self.stdout.write(f"Group team {team.name}: {status}")

        self.stdout.write(self.style.SUCCESS("Seed complete."))

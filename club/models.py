from django.db import models
from django.urls import reverse


class ClubInfo(models.Model):
    """Singleton-ish model holding general club information shown across the
    site. Managed through the admin so non-technical staff can update it
    without touching code.
    """

    name = models.CharField(max_length=120, default="Gurkhali FC")
    tagline = models.CharField(
        max_length=200,
        blank=True,
        help_text='Short motto, e.g. "Himalayan Hearts, Top End Spirits".',
    )
    location = models.CharField(
        max_length=150,
        blank=True,
        help_text='e.g. "Darwin, Northern Territory, Australia".',
    )
    about = models.TextField(
        blank=True, help_text="Longer description shown on the About page."
    )
    founded_year = models.PositiveIntegerField(blank=True, null=True)
    home_ground = models.CharField(max_length=150, blank=True)
    logo = models.ImageField(upload_to="club/", blank=True, null=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)

    class Meta:
        verbose_name = "Club Info"
        verbose_name_plural = "Club Info"

    def __str__(self):
        return self.name


class Player(models.Model):
    class Position(models.TextChoices):
        GOALKEEPER = "GK", "Goalkeeper"
        DEFENDER = "DF", "Defender"
        MIDFIELDER = "MF", "Midfielder"
        FORWARD = "FW", "Forward"
        COACH = "CO", "Coach / Staff"

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True)
    position = models.CharField(
        max_length=2, choices=Position.choices, default=Position.MIDFIELDER
    )
    jersey_number = models.PositiveSmallIntegerField(blank=True, null=True)
    photo = models.ImageField(
        upload_to="players/",
        blank=True,
        null=True,
        help_text="Square headshot works best (e.g. 500x500px). Shown on the squad grid and profile page.",
    )
    bio = models.TextField(
        blank=True,
        help_text="Short player background/description shown on their profile page.",
    )
    date_of_birth = models.DateField(blank=True, null=True)
    is_captain = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(
        default=0, help_text="Lower numbers appear first within their position group."
    )

    class Meta:
        ordering = ["position", "order", "jersey_number", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("club:player_detail", kwargs={"slug": self.slug})


class GalleryCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)

    class Meta:
        verbose_name_plural = "Gallery Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class GalleryImage(models.Model):
    title = models.CharField(max_length=150, blank=True)
    image = models.ImageField(upload_to="gallery/")
    category = models.ForeignKey(
        GalleryCategory,
        on_delete=models.SET_NULL,
        related_name="images",
        blank=True,
        null=True,
    )
    caption = models.CharField(max_length=250, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or f"Gallery image #{self.pk}"


class Match(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        LIVE = "LIVE", "Live now"
        FINISHED = "FINISHED", "Finished"

    opponent = models.CharField(max_length=120, help_text='e.g. "Darwin FC".')
    match_date = models.DateField()
    match_time = models.TimeField(blank=True, null=True)
    venue = models.CharField(max_length=150, blank=True)
    is_home = models.BooleanField(default=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.SCHEDULED,
        help_text="Set to 'Live now' on match day to show it at the top of "
        "the schedule with a live indicator and score.",
    )
    home_score = models.PositiveSmallIntegerField(blank=True, null=True)
    away_score = models.PositiveSmallIntegerField(blank=True, null=True)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["match_date", "match_time"]

    def __str__(self):
        return f"{'vs' if self.is_home else '@'} {self.opponent} ({self.match_date})"

    @property
    def is_played(self):
        return self.home_score is not None and self.away_score is not None

    @property
    def is_live(self):
        return self.status == self.Status.LIVE


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} <{self.email}>"


class CompetitionGroup(models.Model):
    """A World Cup–style group of four teams (e.g. Group A).

    Standings are entered on each GroupTeam and ranked like FIFA group tables:
    points → goal difference → goals for → team name.
    """

    name = models.CharField(max_length=80, help_text='e.g. "Group A".')
    season = models.CharField(
        max_length=120,
        blank=True,
        help_text='Optional label, e.g. "Darwin Cup 2026".',
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Only the active group is shown on the public schedule.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        if self.season:
            return f"{self.name} — {self.season}"
        return self.name

    def standings(self):
        """Return group teams sorted World Cup / FIFA style with position."""
        teams = list(self.teams.all())
        teams.sort(
            key=lambda t: (-t.points, -t.goal_difference, -t.goals_for, t.name.lower())
        )
        rows = []
        for index, team in enumerate(teams, start=1):
            rows.append({"position": index, "team": team})
        return rows


class GroupTeam(models.Model):
    """One of up to four teams in a CompetitionGroup, with WC-table stats."""

    group = models.ForeignKey(
        CompetitionGroup, related_name="teams", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=120)
    is_club = models.BooleanField(
        default=False,
        help_text="Highlight this row as Gurkhali FC on the public table.",
    )
    played = models.PositiveSmallIntegerField(default=0)
    won = models.PositiveSmallIntegerField(default=0)
    drawn = models.PositiveSmallIntegerField(default=0)
    lost = models.PositiveSmallIntegerField(default=0)
    goals_for = models.PositiveSmallIntegerField(default=0)
    goals_against = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["name"]
        unique_together = [("group", "name")]

    def __str__(self):
        return f"{self.name} ({self.group.name})"

    @property
    def points(self):
        return self.won * 3 + self.drawn

    @property
    def goal_difference(self):
        return self.goals_for - self.goals_against


# Fixed squad size for the tournament registration roster — the form shows
# exactly this many Name / Jersey Number slots (no "add player" button).
# Change this single constant to resize the roster everywhere (form, admin,
# Word/PDF exports) at once.
ROSTER_SIZE = 15


class TeamRegistration(models.Model):
    """A team signing up to play in a tournament the club is hosting/running.
    Submitted via the public "Register" section of the site; reviewed and
    actioned (approved/rejected) from the admin.
    """

    class Division(models.TextChoices):
        OPEN_MENS = "OPEN_M", "Open / Men's"
        WOMENS = "WOMENS", "Women's"
        MIXED = "MIXED", "Mixed"
        YOUTH = "YOUTH", "Youth / Junior"
        MASTERS = "MASTERS", "Masters (35+)"
        CORPORATE = "CORP", "Corporate / Social"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending review"
        APPROVED = "APPROVED", "Approved"
        WAITLISTED = "WAITLIST", "Waitlisted"
        REJECTED = "REJECTED", "Rejected"

    tournament_name = models.CharField(
        max_length=150,
        help_text='Which tournament the team is registering for, e.g. "Gurkhali Cup 2026".',
    )
    team_name = models.CharField(max_length=120)
    division = models.CharField(max_length=10, choices=Division.choices, default=Division.OPEN_MENS)
    manager_name = models.CharField(max_length=120, help_text="Team manager or coach's full name.")
    phone = models.CharField(max_length=30)
    email = models.EmailField()
    player_count = models.PositiveSmallIntegerField(
        default=0,
        editable=False,
        help_text="Automatically set to the number of named players in the roster below.",
    )
    home_city = models.CharField(max_length=120, blank=True)
    experience = models.TextField(
        blank=True, help_text="Previous tournament experience, if any (optional)."
    )
    notes = models.TextField(blank=True, help_text="Anything else the organisers should know (optional).")
    agreed_to_rules = models.BooleanField(
        default=False,
        help_text="Team confirmed they agree to the tournament rules and code of conduct.",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.team_name} — {self.tournament_name}"

    def refresh_player_count(self):
        """Recomputes player_count from named roster rows and saves it."""
        count = self.players.exclude(name="").count()
        if count != self.player_count:
            self.player_count = count
            self.save(update_fields=["player_count"])
        return count


class RegisteredPlayer(models.Model):
    """One row of a team's fixed-size roster (see ROSTER_SIZE), submitted
    alongside a TeamRegistration so the club can track who's actually
    playing, not just a headcount guess.
    """

    registration = models.ForeignKey(
        TeamRegistration, related_name="players", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=100, blank=True)
    jersey_number = models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name or "(empty slot)"

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
    """One fixture between two teams (home vs away).

    Group-stage matches link to a CompetitionGroup (table sync). Knockout
    matches use ``stage`` (QF / SF / Final, etc.) like the World Cup.
    """

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        LIVE = "LIVE", "Live now"
        FINISHED = "FINISHED", "Finished"

    class Stage(models.TextChoices):
        GROUP = "GROUP", "Group stage"
        R16 = "R16", "Round of 16"
        QF = "QF", "Quarter-finals"
        SF = "SF", "Semi-finals"
        THIRD = "THIRD", "Third-place play-off"
        FINAL = "FINAL", "Final"

    home_team = models.CharField(
        max_length=120,
        help_text="Home side. For group games, pick from the group's teams.",
    )
    away_team = models.CharField(
        max_length=120,
        help_text="Away side. For group games, pick from the group's teams.",
    )
    group = models.ForeignKey(
        "CompetitionGroup",
        on_delete=models.SET_NULL,
        related_name="matches",
        blank=True,
        null=True,
        help_text="Group stage only — which World Cup group table this "
        "result updates. Leave empty for knockout matches.",
    )
    stage = models.CharField(
        max_length=10,
        choices=Stage.choices,
        default=Stage.GROUP,
        help_text="Group stage or knockout round (World Cup format).",
    )
    bracket_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Order within a knockout round (1 = first match, etc.).",
    )
    match_date = models.DateField()
    match_time = models.TimeField(blank=True, null=True)
    venue = models.CharField(max_length=150, blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.SCHEDULED,
        help_text="Set to 'Live now' on match day, then 'Finished' with "
        "both scores filled in to sync the group table.",
    )
    home_score = models.PositiveSmallIntegerField(blank=True, null=True)
    away_score = models.PositiveSmallIntegerField(blank=True, null=True)
    finished_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Set automatically when status becomes Finished.",
    )
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["match_date", "match_time", "bracket_order"]
        verbose_name_plural = "Matches"

    def __str__(self):
        label = self.get_stage_display() if self.stage != self.Stage.GROUP else ""
        base = f"{self.home_team} vs {self.away_team} ({self.match_date})"
        return f"{label}: {base}" if label else base

    @property
    def is_played(self):
        return self.home_score is not None and self.away_score is not None

    @property
    def is_live(self):
        return self.status == self.Status.LIVE

    @property
    def is_knockout(self):
        return self.stage != self.Stage.GROUP

    @property
    def stage_badge(self):
        """Short label for the public match card end-badge."""
        if self.stage == self.Stage.GROUP:
            return self.group.name if self.group_id else "Group"
        return {
            self.Stage.R16: "R16",
            self.Stage.QF: "QF",
            self.Stage.SF: "SF",
            self.Stage.THIRD: "3rd",
            self.Stage.FINAL: "Final",
        }.get(self.stage, self.get_stage_display())

    @property
    def club_name(self):
        club = ClubInfo.objects.first()
        return club.name if club else "Gurkhali FC"

    @property
    def involves_club(self):
        club = self.club_name.strip().lower()
        return club in {
            self.home_team.strip().lower(),
            self.away_team.strip().lower(),
        }

    @property
    def is_club_home(self):
        return self.home_team.strip().lower() == self.club_name.strip().lower()

    @property
    def winner(self):
        if (
            self.status != self.Status.FINISHED
            or self.home_score is None
            or self.away_score is None
        ):
            return None
        if self.home_score > self.away_score:
            return self.home_team
        if self.away_score > self.home_score:
            return self.away_team
        return None  # draw — rare in knockout without pens

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if (
            self.home_team
            and self.away_team
            and self.home_team.strip().lower() == self.away_team.strip().lower()
        ):
            errors["away_team"] = "Home and away teams must be different."

        if self.status == self.Status.FINISHED:
            if self.home_score is None:
                errors["home_score"] = "Enter the home score before finishing."
            if self.away_score is None:
                errors["away_score"] = "Enter the away score before finishing."

        # Teams no longer need to be pre-added to the group — saving a match
        # with a Group selected will add them automatically (lucky-draw flow).

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        from django.utils import timezone

        previous_status = None
        if self.pk:
            previous_status = (
                Match.objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )

        # Blank scores on a finished match were blocking table sync — treat
        # missing values as 0 so a result always updates standings.
        if self.status == self.Status.FINISHED:
            if self.home_score is None:
                self.home_score = 0
            if self.away_score is None:
                self.away_score = 0
            if previous_status != self.Status.FINISHED or self.finished_at is None:
                if previous_status != self.Status.FINISHED:
                    self.finished_at = timezone.now()
                elif self.finished_at is None:
                    self.finished_at = timezone.now()
        else:
            self.finished_at = None

        # Knockout fixtures are not tied to a group table.
        if self.stage != self.Stage.GROUP:
            self.group = None
        elif not self.group_id and self.home_team and self.away_team:
            # Auto-attach the group when both teams already sit in the same one.
            self.group = self._detect_shared_group()

        super().save(*args, **kwargs)

        # After lucky draw: picking a Group on the fixture places both teams
        # into that group's table automatically (using the registration names).
        if self.stage == self.Stage.GROUP and self.group_id:
            self._ensure_teams_in_group()

        from .standings import sync_standings_after_match

        sync_standings_after_match(self)

        # Progressive knockout: finishing the last group match schedules QF;
        # finishing a full knockout round schedules the next (SF / Final).
        from .knockout import maybe_progress_knockout

        maybe_progress_knockout(self, previous_status=previous_status)

    def _ensure_teams_in_group(self):
        if not self.group_id:
            return
        for team_name in (self.home_team, self.away_team):
            if team_name and team_name.strip():
                self.group.ensure_team(team_name.strip())

    def _detect_shared_group(self):
        home_groups = set(
            GroupTeam.objects.filter(name__iexact=self.home_team.strip()).values_list(
                "group_id", flat=True
            )
        )
        away_groups = set(
            GroupTeam.objects.filter(name__iexact=self.away_team.strip()).values_list(
                "group_id", flat=True
            )
        )
        shared = home_groups & away_groups
        if len(shared) == 1:
            return CompetitionGroup.objects.filter(pk=shared.pop()).first()
        return None


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

    Team W/D/L/GF/GA are synced from finished Match scores between two
    teams in this group, then ranked: points → GD → GF → name.
    """

    name = models.CharField(max_length=80, help_text='e.g. "Group A".')
    season = models.CharField(
        max_length=120,
        blank=True,
        help_text='Optional label, e.g. "Darwin Cup 2026".',
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Active groups (up to four) appear in the Schedule tables grid.",
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

    def ensure_team(self, team_name):
        """Add an approved/registered team name to this group if missing.

        Case-insensitive match reuses an existing row so "Chillax 1" won't
        duplicate "Chillax-1" if that spelling is already in the group —
        but new names (e.g. Gurkhali FC Red) are added as-is.
        """
        name = (team_name or "").strip()
        if not name:
            return None
        existing = self.teams.filter(name__iexact=name).first()
        if existing:
            return existing
        club = ClubInfo.objects.first()
        is_club = bool(
            club and name.lower() == club.name.strip().lower()
        )
        return GroupTeam.objects.create(group=self, name=name, is_club=is_club)


class GroupTeam(models.Model):
    """One of up to four teams in a CompetitionGroup, with WC-table stats.

    Stats are auto-calculated from finished matches whose home/away team
    names match GroupTeam names in this group.
    """

    group = models.ForeignKey(
        CompetitionGroup, related_name="teams", on_delete=models.CASCADE
    )
    name = models.CharField(
        max_length=120,
        help_text="Must match Match home/away team names for score sync.",
    )
    is_club = models.BooleanField(
        default=False,
        help_text="Highlight this row as Gurkhali FC on the public table.",
    )
    played = models.PositiveSmallIntegerField(
        default=0, help_text="Auto-updated from finished matches."
    )
    won = models.PositiveSmallIntegerField(
        default=0, help_text="Auto-updated from finished matches."
    )
    drawn = models.PositiveSmallIntegerField(
        default=0, help_text="Auto-updated from finished matches."
    )
    lost = models.PositiveSmallIntegerField(
        default=0, help_text="Auto-updated from finished matches."
    )
    goals_for = models.PositiveSmallIntegerField(
        default=0, help_text="Auto-updated from finished matches."
    )
    goals_against = models.PositiveSmallIntegerField(
        default=0, help_text="Auto-updated from finished matches."
    )

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
# exactly this many Name slots (jersey optional). Change this single constant
# to resize the roster everywhere (form, admin, Word/PDF exports) at once.
ROSTER_SIZE = 12

# Public registration is locked to this tournament / division.
DEFAULT_TOURNAMENT_NAME = "Dashain Cup 2026"
APPROVED_TEAMS_FOR_SCHEDULE = 16


class TeamRegistration(models.Model):
    """A team signing up to play in a tournament the club is hosting/running.
    Submitted via the public "Register" section of the site; reviewed and
    actioned (approved/rejected) from the admin.
    """

    class Division(models.TextChoices):
        OPEN_7A = "OPEN_7A", "Open 7A-side football competition"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending review"
        APPROVED = "APPROVED", "Approved"
        WAITLISTED = "WAITLIST", "Waitlisted"
        REJECTED = "REJECTED", "Rejected"

    tournament_name = models.CharField(
        max_length=150,
        default=DEFAULT_TOURNAMENT_NAME,
        help_text='Fixed for this season — "Dashain Cup 2026".',
    )
    team_name = models.CharField(max_length=120)
    division = models.CharField(
        max_length=10,
        choices=Division.choices,
        default=Division.OPEN_7A,
    )
    manager_name = models.CharField(max_length=120, help_text="Team manager or coach's full name.")
    phone = models.CharField(max_length=30)
    email = models.EmailField(
        help_text="Must be a valid Gmail address (example@gmail.com)."
    )
    player_count = models.PositiveSmallIntegerField(
        default=0,
        editable=False,
        help_text="Automatically set to the number of named players in the roster below.",
    )
    home_city = models.CharField(max_length=120)
    experience = models.TextField(
        help_text="Previous tournament experience (required)."
    )
    notes = models.TextField(
        help_text="Anything else the organisers should know (required — write N/A if none)."
    )
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

    @classmethod
    def approved_team_names(cls):
        """Distinct team names from Approved registrations only (for fixtures)."""
        return list(
            cls.objects.filter(status=cls.Status.APPROVED)
            .exclude(team_name="")
            .order_by("team_name")
            .values_list("team_name", flat=True)
            .distinct()
        )

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


class KnockoutBracket(models.Model):
    """Admin hub for the World Cup knockout phase.

    Appears as "Knockout" in the Club admin. Shows top-2 qualifiers from
    each competition group and generates the knockout fixtures.
    """

    name = models.CharField(max_length=120, default="Knockout Stage")
    season = models.CharField(
        max_length=120,
        blank=True,
        help_text='e.g. "Darwin Cup 2026".',
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Show this knockout on the public schedule when fixtures exist.",
    )
    include_third_place = models.BooleanField(
        default=True,
        help_text="Create a 3rd-place play-off alongside the Final.",
    )
    start_date = models.DateField(
        blank=True,
        null=True,
        help_text="First knockout matchday. Defaults to 7 days from today.",
    )
    generated_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Set automatically when fixtures are generated.",
    )

    class Meta:
        verbose_name = "Knockout"
        verbose_name_plural = "Knockout"
        ordering = ["-is_active", "name"]

    def __str__(self):
        if self.season:
            return f"{self.name} — {self.season}"
        return self.name

    @classmethod
    def get_solo(cls):
        """Return the primary knockout hub, creating one if needed."""
        obj = cls.objects.filter(is_active=True).first()
        if obj:
            return obj
        obj = cls.objects.first()
        if obj:
            return obj
        return cls.objects.create(name="Knockout Stage", season="Darwin Cup 2026")

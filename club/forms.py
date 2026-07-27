import re

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import (
    DEFAULT_TOURNAMENT_NAME,
    CompetitionGroup,
    ContactMessage,
    GroupTeam,
    Match,
    RegisteredPlayer,
    ROSTER_SIZE,
    TeamRegistration,
)


def _approved_team_choices(extra_names=None):
    """Build select choices from Approved registrations (+ optional extras)."""
    approved = TeamRegistration.approved_team_names()
    choices = [("", "---------")] + [(name, name) for name in approved]
    seen = {name.lower() for name in approved}
    for name in extra_names or []:
        cleaned = (name or "").strip()
        if cleaned and cleaned.lower() not in seen:
            choices.append((cleaned, f"{cleaned} (not in approved list)"))
            seen.add(cleaned.lower())
    return choices, approved


def team_names_for_group(group):
    """Return ordered team names belonging to a competition group."""
    if not group:
        return []
    return list(group.teams.order_by("name").values_list("name", flat=True))


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "John Smith"}),
            "email": forms.EmailInput(attrs={"placeholder": "john@example.com"}),
            "message": forms.Textarea(
                attrs={"placeholder": "Write your message here...", "rows": 6}
            ),
        }


class TeamRegistrationForm(forms.ModelForm):
    agreed_to_rules = forms.BooleanField(
        required=True,
        label="I confirm my team agrees to the tournament rules and code of conduct.",
        error_messages={"required": "You must agree to the rules to register."},
    )

    class Meta:
        model = TeamRegistration
        fields = [
            "team_name",
            "manager_name",
            "phone",
            "email",
            "home_city",
            "experience",
            "notes",
            "agreed_to_rules",
        ]
        widgets = {
            "team_name": forms.TextInput(
                attrs={
                    "placeholder": "Your team's name",
                    "autocomplete": "organization",
                }
            ),
            "manager_name": forms.TextInput(
                attrs={"placeholder": "Full name", "autocomplete": "name"}
            ),
            "phone": forms.TextInput(
                attrs={
                    "placeholder": "e.g. 0400 000 000",
                    "autocomplete": "tel",
                    "inputmode": "tel",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "yourteam@gmail.com",
                    "autocomplete": "email",
                }
            ),
            "home_city": forms.TextInput(
                attrs={"placeholder": "e.g. Darwin", "autocomplete": "address-level2"}
            ),
            "experience": forms.Textarea(
                attrs={
                    "placeholder": "List previous tournaments or write N/A",
                    "rows": 3,
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "placeholder": "Anything else we should know? Write N/A if none",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "agreed_to_rules":
                continue
            field.required = True
            field.widget.attrs.setdefault("required", "required")
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} register-input".strip()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        # Gmail-style address check: valid local-part + @gmail.com only.
        if not re.fullmatch(r"[a-z0-9._%+\-]+@gmail\.com", email):
            raise ValidationError(
                "Please enter a valid Gmail address ending in @gmail.com."
            )
        local = email.split("@", 1)[0]
        if local.startswith(".") or local.endswith(".") or ".." in local:
            raise ValidationError("That Gmail address looks invalid. Please check it.")
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        digits = re.sub(r"\D", "", phone)
        if len(digits) < 8:
            raise ValidationError("Enter a valid phone number (at least 8 digits).")
        return phone

    def clean_team_name(self):
        name = (self.cleaned_data.get("team_name") or "").strip()
        if len(name) < 2:
            raise ValidationError("Enter your full team name.")
        # Team name is the unique id — one registration per team (case-insensitive).
        qs = TeamRegistration.objects.filter(team_name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                "This team name is already registered. Each team can only "
                "register once — choose a different name if this isn't your team."
            )
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tournament_name = DEFAULT_TOURNAMENT_NAME
        instance.division = TeamRegistration.Division.OPEN_7A
        if commit:
            instance.save()
        return instance


class RegisteredPlayerForm(forms.ModelForm):
    class Meta:
        model = RegisteredPlayer
        fields = ["name", "jersey_number"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Player full name",
                    "class": "register-input roster-name",
                    "required": "required",
                }
            ),
            "jersey_number": forms.NumberInput(
                attrs={
                    "placeholder": "No.",
                    "min": 0,
                    "max": 99,
                    "class": "register-input roster-jersey",
                    "inputmode": "numeric",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = True
        self.fields["jersey_number"].required = False

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise ValidationError("Player name is required.")
        return name


class BaseRegisteredPlayerFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        named_players = []
        for form in self.forms:
            cleaned = getattr(form, "cleaned_data", None)
            if not cleaned:
                continue
            name = (cleaned.get("name") or "").strip()
            if name:
                named_players.append(name)
        if len(named_players) < ROSTER_SIZE:
            raise ValidationError(
                f"All {ROSTER_SIZE} player names are required "
                f"({len(named_players)} of {ROSTER_SIZE} filled)."
            )


# Fixed number of roster rows (see club.models.ROSTER_SIZE).
RegisteredPlayerFormSet = inlineformset_factory(
    TeamRegistration,
    RegisteredPlayer,
    form=RegisteredPlayerForm,
    formset=BaseRegisteredPlayerFormSet,
    extra=ROSTER_SIZE,
    min_num=ROSTER_SIZE,
    max_num=ROSTER_SIZE,
    validate_min=True,
    validate_max=True,
    can_delete=False,
)

class MatchAdminForm(forms.ModelForm):
    """Fixture form: group-filtered teams for group stage; free text for knockout."""

    group = forms.ModelChoiceField(
        queryset=CompetitionGroup.objects.all(),
        required=False,
        empty_label="--------- Select a group (group stage) ---------",
        help_text="Required for group stage. Leave empty for knockout matches.",
    )
    home_team = forms.CharField(label="Home team", max_length=120)
    away_team = forms.CharField(label="Away team", max_length=120)

    class Meta:
        model = Match
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from django.urls import NoReverseMatch, reverse

        try:
            self.fields["group"].widget.attrs["data-teams-url"] = reverse(
                "admin:club_match_teams_for_group"
            )
        except NoReverseMatch:
            pass

        stage = self._resolve_stage()
        group = self._resolve_group()
        instance = self.instance if getattr(self.instance, "pk", None) else None

        # Group stage: constrain Home/Away to the selected group's teams.
        # Knockout: keep plain text inputs (placeholders like "Winner QF1" allowed).
        if stage == Match.Stage.GROUP:
            team_names = team_names_for_group(group)
            extras = []
            if instance:
                for value in (instance.home_team, instance.away_team):
                    if value and value not in team_names:
                        extras.append(value)
            if group:
                choices = [("", "---------")] + [(name, name) for name in team_names]
                for name in extras:
                    choices.append((name, f"{name} (not in this group anymore)"))
                tip = "Teams currently in the selected group."
            else:
                choices = [("", "--------- Select a group first ---------")]
                tip = "Select a group first to load its teams."
            self.fields["home_team"] = forms.ChoiceField(
                choices=choices, label="Home team", help_text=tip
            )
            self.fields["away_team"] = forms.ChoiceField(
                choices=choices, label="Away team", help_text=tip
            )
            if group and not team_names:
                empty_tip = (
                    "This group has no teams yet — add them under Competition "
                    "groups after the lucky draw."
                )
                self.fields["home_team"].help_text = empty_tip
                self.fields["away_team"].help_text = empty_tip
        else:
            self.fields["home_team"].help_text = (
                "Knockout home team (or placeholder until advanced)."
            )
            self.fields["away_team"].help_text = (
                "Knockout away team (or placeholder until advanced)."
            )
            self.fields["group"].help_text = (
                "Leave empty for knockout — group tables are not updated."
            )

    def _resolve_group(self):
        if self.is_bound:
            group_id = self.data.get(self.add_prefix("group")) or self.data.get("group")
            if group_id:
                return CompetitionGroup.objects.filter(pk=group_id).first()
        elif self.instance and self.instance.group_id:
            return self.instance.group
        return None

    def _resolve_stage(self):
        if self.is_bound:
            return self.data.get(self.add_prefix("stage")) or self.data.get(
                "stage", Match.Stage.GROUP
            )
        if self.instance and self.instance.pk:
            return self.instance.stage
        return Match.Stage.GROUP

    def clean(self):
        cleaned = super().clean()
        stage = cleaned.get("stage") or Match.Stage.GROUP
        group = cleaned.get("group")
        home = (cleaned.get("home_team") or "").strip()
        away = (cleaned.get("away_team") or "").strip()

        if stage == Match.Stage.GROUP:
            if not group:
                self.add_error("group", "Select a group for group-stage matches.")
                return cleaned
            allowed = {name.lower() for name in team_names_for_group(group)}
            instance = self.instance if getattr(self.instance, "pk", None) else None
            for field_name, value in (("home_team", home), ("away_team", away)):
                if not value:
                    continue
                saved = (
                    (getattr(instance, field_name, "") or "").strip().lower()
                    if instance
                    else ""
                )
                if value.lower() not in allowed and value.lower() != saved:
                    self.add_error(
                        field_name,
                        f'"{value}" is not in {group.name}. '
                        "Add the team to that group after the lucky draw.",
                    )
        else:
            cleaned["group"] = None

        if home and away and home.lower() == away.lower():
            self.add_error("away_team", "Home and away teams must be different.")

        return cleaned


class GroupTeamAdminForm(forms.ModelForm):
    """Lucky-draw group assignment: pick from Approved registrations only."""

    name = forms.ChoiceField(
        choices=[],
        label="Team",
        help_text="Approved registered teams only (set after the lucky draw).",
    )

    class Meta:
        model = GroupTeam
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        extras = []
        instance = kwargs.get("instance") or getattr(self, "instance", None)
        if instance and instance.pk and instance.name:
            extras = [instance.name]
        choices, approved = _approved_team_choices(extras)
        self.fields["name"].choices = choices
        if not approved:
            self.fields["name"].help_text = (
                "No approved teams yet — approve a registration first."
            )

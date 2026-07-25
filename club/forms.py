from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import (
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
            "tournament_name",
            "team_name",
            "division",
            "manager_name",
            "phone",
            "email",
            "home_city",
            "experience",
            "notes",
            "agreed_to_rules",
        ]
        widgets = {
            "tournament_name": forms.TextInput(attrs={"placeholder": "e.g. Gurkhali Cup 2026"}),
            "team_name": forms.TextInput(attrs={"placeholder": "Your team's name"}),
            "manager_name": forms.TextInput(attrs={"placeholder": "Full name"}),
            "phone": forms.TextInput(attrs={"placeholder": "e.g. 0400 000 000"}),
            "email": forms.EmailInput(attrs={"placeholder": "team@example.com"}),
            "home_city": forms.TextInput(attrs={"placeholder": "e.g. Darwin"}),
            "experience": forms.Textarea(
                attrs={
                    "placeholder": "Optional — any previous tournaments you've played in",
                    "rows": 3,
                }
            ),
            "notes": forms.Textarea(
                attrs={"placeholder": "Anything else we should know? (optional)", "rows": 3}
            ),
        }


class RegisteredPlayerForm(forms.ModelForm):
    class Meta:
        model = RegisteredPlayer
        fields = ["name", "jersey_number"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Player full name"}),
            "jersey_number": forms.NumberInput(
                attrs={"placeholder": "#", "min": 0, "max": 99}
            ),
        }


class BaseRegisteredPlayerFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        named_players = 0
        for form in self.forms:
            cleaned = getattr(form, "cleaned_data", None)
            if cleaned and cleaned.get("name", "").strip():
                named_players += 1
        if named_players == 0:
            raise ValidationError(
                "Please list at least one player in the roster below."
            )


# Fixed number of roster rows (see club.models.ROSTER_SIZE) — no "add
# player" button, exactly ROSTER_SIZE Name/Jersey Number slots every time.
RegisteredPlayerFormSet = inlineformset_factory(
    TeamRegistration,
    RegisteredPlayer,
    form=RegisteredPlayerForm,
    formset=BaseRegisteredPlayerFormSet,
    extra=ROSTER_SIZE,
    max_num=ROSTER_SIZE,
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

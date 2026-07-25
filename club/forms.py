from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import (
    ContactMessage,
    Match,
    RegisteredPlayer,
    ROSTER_SIZE,
    TeamRegistration,
)


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
                attrs={"placeholder": "Optional — any previous tournaments you've played in", "rows": 3}
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
            "jersey_number": forms.NumberInput(attrs={"placeholder": "#", "min": 0, "max": 99}),
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
    """Home/Away pickers limited to Approved tournament registrations.

    Pending, waitlisted, and rejected teams never appear in the dropdowns.
    """

    home_team = forms.ChoiceField(
        choices=[],
        label="Home team",
        help_text="Approved registered teams only.",
    )
    away_team = forms.ChoiceField(
        choices=[],
        label="Away team",
        help_text="Approved registered teams only.",
    )

    class Meta:
        model = Match
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        approved = TeamRegistration.approved_team_names()
        choices = [("", "---------")] + [(name, name) for name in approved]

        # Keep a legacy/saved name selectable so existing fixtures remain editable
        # even if that registration was later un-approved.
        instance = kwargs.get("instance") or getattr(self, "instance", None)
        if instance and instance.pk:
            for field_name in ("home_team", "away_team"):
                current = (getattr(instance, field_name, "") or "").strip()
                if current and current not in approved:
                    choices.append(
                        (current, f"{current} (no longer approved)")
                    )

        self.fields["home_team"].choices = choices
        self.fields["away_team"].choices = choices

        if not approved:
            self.fields["home_team"].help_text = (
                "No approved teams yet — approve a registration first."
            )
            self.fields["away_team"].help_text = (
                "No approved teams yet — approve a registration first."
            )

    def clean(self):
        cleaned = super().clean()
        home = (cleaned.get("home_team") or "").strip()
        away = (cleaned.get("away_team") or "").strip()
        approved = {name.lower() for name in TeamRegistration.approved_team_names()}

        # Allow currently saved names through (legacy fixtures); block new picks
        # that aren't approved.
        instance = self.instance
        for field_name, value in (("home_team", home), ("away_team", away)):
            if not value:
                continue
            saved = (
                (getattr(instance, field_name, "") or "").strip().lower()
                if instance and instance.pk
                else ""
            )
            if value.lower() not in approved and value.lower() != saved:
                self.add_error(
                    field_name,
                    "Only teams with an Approved registration can be selected.",
                )

        if home and away and home.lower() == away.lower():
            self.add_error("away_team", "Home and away teams must be different.")

        return cleaned

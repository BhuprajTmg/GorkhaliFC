from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import ContactMessage, RegisteredPlayer, ROSTER_SIZE, TeamRegistration


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

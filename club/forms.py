from django import forms

from .models import ContactMessage, TeamRegistration


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
            "player_count",
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
            "player_count": forms.NumberInput(attrs={"placeholder": "e.g. 14", "min": 1}),
            "home_city": forms.TextInput(attrs={"placeholder": "e.g. Darwin"}),
            "experience": forms.Textarea(
                attrs={"placeholder": "Optional — any previous tournaments you've played in", "rows": 3}
            ),
            "notes": forms.Textarea(
                attrs={"placeholder": "Anything else we should know? (optional)", "rows": 3}
            ),
        }

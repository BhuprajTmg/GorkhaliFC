from django import forms

from .models import ContactMessage


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

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .emails import send_contact_notification, send_registration_notification
from .forms import ContactForm, TeamRegistrationForm
from .models import ClubInfo, GalleryCategory, GalleryImage, Match, Player


def home(request):
    """Single-page site: hero + about + players + schedule + register +
    photos + contact, all rendered as sections on one scrollable page,
    navigated via anchor links (matches the original site's #about /
    #players / ... URLs).
    """
    club = ClubInfo.objects.first()
    # Distinct prefixes keep field ids/names unique since both forms render
    # on the same one-page site (otherwise "email", "name", etc. would
    # collide between the two forms).
    contact_form = ContactForm(prefix="contact")
    registration_form = TeamRegistrationForm(prefix="registration")

    if request.method == "POST":
        form_name = request.POST.get("form_name")

        if form_name == "registration":
            registration_form = TeamRegistrationForm(request.POST, prefix="registration")
            if registration_form.is_valid():
                registration = registration_form.save()
                send_registration_notification(registration, club)
                messages.success(
                    request,
                    f"Thanks, {registration.team_name}! Your registration for "
                    f"{registration.tournament_name} has been received — we'll "
                    f"be in touch soon.",
                )
                return redirect(f"{request.path}#register")
        else:
            contact_form = ContactForm(request.POST, prefix="contact")
            if contact_form.is_valid():
                contact_message = contact_form.save()
                send_contact_notification(contact_message, club)
                messages.success(
                    request, "Thanks for reaching out! We'll get back to you soon."
                )
                return redirect(f"{request.path}#contact")

    active_players = Player.objects.filter(is_active=True)
    grouped_players = []
    for value, label in Player.Position.choices:
        group_players = [p for p in active_players if p.position == value]
        if group_players:
            grouped_players.append({"label": label, "players": group_players})

    today = timezone.now().date()

    context = {
        "club": club,
        "players_count": active_players.count(),
        "grouped_players": grouped_players,
        "upcoming_matches": Match.objects.filter(match_date__gte=today),
        "past_matches": Match.objects.filter(match_date__lt=today).order_by("-match_date"),
        "next_match": Match.objects.filter(match_date__gte=today).first(),
        "categories": GalleryCategory.objects.all(),
        "images": GalleryImage.objects.all(),
        "form": contact_form,
        "registration_form": registration_form,
    }
    return render(request, "club/home.html", context)


def player_detail(request, slug):
    player = get_object_or_404(Player, slug=slug, is_active=True)
    context = {
        "club": ClubInfo.objects.first(),
        "player": player,
    }
    return render(request, "club/player_detail.html", context)

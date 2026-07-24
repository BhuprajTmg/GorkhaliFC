from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ContactForm
from .models import ClubInfo, GalleryCategory, GalleryImage, Match, Player


def home(request):
    """Single-page site: hero + about + players + schedule + photos +
    contact, all rendered as sections on one scrollable page, navigated via
    anchor links (matches the original site's #about / #players / ... URLs).
    """
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, "Thanks for reaching out! We'll get back to you soon."
            )
            return redirect(f"{request.path}#contact")
    else:
        form = ContactForm()

    active_players = Player.objects.filter(is_active=True)
    grouped_players = []
    for value, label in Player.Position.choices:
        group_players = [p for p in active_players if p.position == value]
        if group_players:
            grouped_players.append({"label": label, "players": group_players})

    today = timezone.now().date()

    context = {
        "club": ClubInfo.objects.first(),
        "players_count": active_players.count(),
        "grouped_players": grouped_players,
        "upcoming_matches": Match.objects.filter(match_date__gte=today),
        "past_matches": Match.objects.filter(match_date__lt=today).order_by("-match_date"),
        "next_match": Match.objects.filter(match_date__gte=today).first(),
        "categories": GalleryCategory.objects.all(),
        "images": GalleryImage.objects.all(),
        "form": form,
    }
    return render(request, "club/home.html", context)


def player_detail(request, slug):
    player = get_object_or_404(Player, slug=slug, is_active=True)
    context = {
        "club": ClubInfo.objects.first(),
        "player": player,
    }
    return render(request, "club/player_detail.html", context)

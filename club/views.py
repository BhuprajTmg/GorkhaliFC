from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ContactForm
from .models import ClubInfo, GalleryCategory, GalleryImage, Match, Player


def home(request):
    context = {
        "club": ClubInfo.objects.first(),
        "players_count": Player.objects.filter(is_active=True).count(),
        "next_match": Match.objects.filter(match_date__gte=timezone.now().date()).first(),
        "gallery_preview": GalleryImage.objects.all()[:6],
    }
    return render(request, "club/home.html", context)


def about(request):
    context = {
        "club": ClubInfo.objects.first(),
        "players_count": Player.objects.filter(is_active=True).count(),
    }
    return render(request, "club/about.html", context)


def players(request):
    active_players = Player.objects.filter(is_active=True)
    grouped = []
    for value, label in Player.Position.choices:
        group_players = [p for p in active_players if p.position == value]
        if group_players:
            grouped.append({"label": label, "players": group_players})
    context = {
        "club": ClubInfo.objects.first(),
        "grouped_players": grouped,
    }
    return render(request, "club/players.html", context)


def player_detail(request, slug):
    player = get_object_or_404(Player, slug=slug, is_active=True)
    context = {
        "club": ClubInfo.objects.first(),
        "player": player,
    }
    return render(request, "club/player_detail.html", context)


def schedule(request):
    today = timezone.now().date()
    context = {
        "club": ClubInfo.objects.first(),
        "upcoming_matches": Match.objects.filter(match_date__gte=today),
        "past_matches": Match.objects.filter(match_date__lt=today).order_by("-match_date"),
    }
    return render(request, "club/schedule.html", context)


def photos(request):
    categories = GalleryCategory.objects.all()
    selected = request.GET.get("category")
    images = GalleryImage.objects.all()
    if selected:
        images = images.filter(category__slug=selected)
    context = {
        "club": ClubInfo.objects.first(),
        "categories": categories,
        "images": images,
        "selected": selected,
    }
    return render(request, "club/photos.html", context)


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, "Thanks for reaching out! We'll get back to you soon."
            )
            return redirect("club:contact")
    else:
        form = ContactForm()
    context = {
        "club": ClubInfo.objects.first(),
        "form": form,
    }
    return render(request, "club/contact.html", context)

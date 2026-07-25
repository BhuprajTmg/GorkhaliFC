from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .emails import send_contact_notification, send_registration_notification
from .forms import ContactForm, RegisteredPlayerFormSet, TeamRegistrationForm
from .models import (
    ClubInfo,
    CompetitionGroup,
    GalleryCategory,
    GalleryImage,
    Match,
    Player,
    TeamRegistration,
)


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
    roster_formset = RegisteredPlayerFormSet(instance=TeamRegistration(), prefix="roster")

    if request.method == "POST":
        form_name = request.POST.get("form_name")

        if form_name == "registration":
            registration_form = TeamRegistrationForm(request.POST, prefix="registration")
            roster_formset = RegisteredPlayerFormSet(
                request.POST, instance=TeamRegistration(), prefix="roster"
            )
            if registration_form.is_valid() and roster_formset.is_valid():
                registration = registration_form.save()
                roster_formset.instance = registration
                roster_formset.save()
                registration.refresh_player_count()
                send_registration_notification(registration, club)
                messages.success(
                    request,
                    f"Thanks, {registration.team_name}! Your registration for "
                    f"{registration.tournament_name} has been received — we'll "
                    f"be in touch soon.",
                )
                return redirect(f"{request.path}#register")
            messages.error(
                request,
                "Your registration couldn't be submitted — please check the "
                "highlighted fields below and try again.",
            )
        else:
            contact_form = ContactForm(request.POST, prefix="contact")
            if contact_form.is_valid():
                contact_message = contact_form.save()
                send_contact_notification(contact_message, club)
                messages.success(
                    request, "Thanks for reaching out! We'll get back to you soon."
                )
                return redirect(f"{request.path}#contact")
            messages.error(
                request,
                "Your message couldn't be sent — please check the highlighted "
                "fields below and try again.",
            )

    active_players = Player.objects.filter(is_active=True)
    grouped_players = []
    for value, label in Player.Position.choices:
        group_players = [p for p in active_players if p.position == value]
        if group_players:
            grouped_players.append({"label": label, "players": group_players})

    # Schedule: live matches always shown first, then the very next
    # scheduled match is highlighted as "Next Match", then the rest of the
    # upcoming fixtures, then finished matches as results. Driven by the
    # Match.status field (set from the admin), not just today's date, so
    # a match manually marked "Live now" always surfaces at the top.
    live_matches = list(Match.objects.filter(status=Match.Status.LIVE))
    scheduled_matches = list(Match.objects.filter(status=Match.Status.SCHEDULED))
    next_match = scheduled_matches[0] if scheduled_matches else None
    upcoming_matches = scheduled_matches[1:] if next_match else []
    past_matches = Match.objects.filter(status=Match.Status.FINISHED).order_by("-match_date")

    # World Cup–format group table (four teams). Show the first active group.
    competition_group = (
        CompetitionGroup.objects.filter(is_active=True)
        .prefetch_related("teams")
        .first()
    )
    group_standings = competition_group.standings() if competition_group else []

    context = {
        "club": club,
        "players_count": active_players.count(),
        "grouped_players": grouped_players,
        "live_matches": live_matches,
        "next_match": next_match,
        "upcoming_matches": upcoming_matches,
        "past_matches": past_matches,
        "competition_group": competition_group,
        "group_standings": group_standings,
        "categories": GalleryCategory.objects.all(),
        "images": GalleryImage.objects.all(),
        "form": contact_form,
        "registration_form": registration_form,
        "roster_formset": roster_formset,
    }
    return render(request, "club/home.html", context)


def player_detail(request, slug):
    player = get_object_or_404(Player, slug=slug, is_active=True)
    context = {
        "club": ClubInfo.objects.first(),
        "player": player,
    }
    return render(request, "club/player_detail.html", context)

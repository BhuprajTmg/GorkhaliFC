from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .emails import (
    email_delivery_enabled,
    send_contact_notification,
    send_registration_notification,
    send_registration_received_confirmation,
)
from .forms import ContactForm, RegisteredPlayerFormSet, TeamRegistrationForm
from .models import (
    DEFAULT_TOURNAMENT_NAME,
    ROSTER_SIZE,
    ClubInfo,
    CompetitionGroup,
    GalleryCategory,
    GalleryImage,
    Player,
    TeamRegistration,
)
from .schedule import build_match_schedule

# One successful tournament registration per browser session.
REGISTRATION_SESSION_KEY = "dashain_registration_submitted"


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
    registration_already_submitted = bool(
        request.session.get(REGISTRATION_SESSION_KEY)
    )
    home_url = reverse("club:home")

    if request.method == "POST":
        form_name = request.POST.get("form_name")

        if form_name == "registration":
            if request.session.get(REGISTRATION_SESSION_KEY):
                messages.info(
                    request,
                    "You have already submitted a team registration in this "
                    "browser session. Only one registration is allowed per session.",
                )
                return redirect(home_url)

            registration_form = TeamRegistrationForm(request.POST, prefix="registration")
            roster_formset = RegisteredPlayerFormSet(
                request.POST, instance=TeamRegistration(), prefix="roster"
            )
            if registration_form.is_valid() and roster_formset.is_valid():
                try:
                    with transaction.atomic():
                        registration = registration_form.save()
                        roster_formset.instance = registration
                        roster_formset.save()
                        registration.refresh_player_count()
                except IntegrityError:
                    # Race: two rapid submits with the same team name.
                    registration_form.add_error(
                        "team_name",
                        "This team name is already registered. Each team can "
                        "only register once.",
                    )
                else:
                    send_registration_notification(registration, club)
                    confirmation_queued = send_registration_received_confirmation(
                        registration, club
                    )
                    request.session[REGISTRATION_SESSION_KEY] = {
                        "team_name": registration.team_name,
                        "email": registration.email,
                        "id": registration.pk,
                    }
                    request.session.modified = True
                    if email_delivery_enabled() and confirmation_queued:
                        messages.success(
                            request,
                            f"Thanks, {registration.team_name}! Your registration for "
                            f"{registration.tournament_name} is being reviewed — check "
                            f"your Gmail for confirmation.",
                        )
                    else:
                        messages.success(
                            request,
                            f"Thanks, {registration.team_name}! Your registration for "
                            f"{registration.tournament_name} was received and is "
                            f"being reviewed.",
                        )
                    # No #hash — avoids page scroll jump under the success popup.
                    return redirect(home_url)
            # Invalid: re-render with the register modal open and field errors.
            # Skip the site-wide message popup so the page doesn't jump.
        else:
            contact_form = ContactForm(request.POST, prefix="contact")
            if contact_form.is_valid():
                contact_message = contact_form.save()
                send_contact_notification(contact_message, club)
                messages.success(
                    request, "Thanks for reaching out! We'll get back to you soon."
                )
                return redirect(home_url)
            # Invalid contact: show inline field errors only (no scroll popup).

    registration_already_submitted = bool(
        request.session.get(REGISTRATION_SESSION_KEY)
    )

    active_players = Player.objects.filter(is_active=True)
    grouped_players = []
    for value, label in Player.Position.choices:
        group_players = [p for p in active_players if p.position == value]
        if group_players:
            grouped_players.append({"label": label, "players": group_players})

    # Schedule: only the head of the fixture queue is shown as "Next Match".
    # Later games stay hidden until the preceding match is marked Finished
    # (see club.schedule.build_match_schedule). Live matches still surface
    # immediately while they are in progress.
    schedule = build_match_schedule()

    # World Cup–format group tables: up to four active groups shown as a
    # compact interactive grid; each expands into a full standings view.
    # Stats are kept in sync from finished Match scores (see club.standings).
    competition_groups = []
    for group in (
        CompetitionGroup.objects.filter(is_active=True)
        .prefetch_related("teams")
        .order_by("name")[:4]
    ):
        competition_groups.append({"group": group, "standings": group.standings()})

    context = {
        "club": club,
        "players_count": active_players.count(),
        "grouped_players": grouped_players,
        "live_matches": schedule["live_matches"],
        "next_match": schedule["next_match"],
        "upcoming_matches": schedule["upcoming_matches"],
        "knockout_rounds": schedule["knockout_rounds"],
        "knockout_bracket": schedule["knockout_bracket"],
        "past_matches": schedule["past_matches"],
        "finished_visible_minutes": schedule["finished_visible_minutes"],
        "competition_groups": competition_groups,
        "categories": GalleryCategory.objects.all(),
        "images": GalleryImage.objects.all(),
        "form": contact_form,
        "registration_form": registration_form,
        "roster_formset": roster_formset,
        "registration_already_submitted": registration_already_submitted,
        "default_tournament_name": DEFAULT_TOURNAMENT_NAME,
        "default_division_label": TeamRegistration.Division.OPEN_7A.label,
        "roster_size": ROSTER_SIZE,
    }
    return render(request, "club/home.html", context)


def player_detail(request, slug):
    player = get_object_or_404(Player, slug=slug, is_active=True)
    context = {
        "club": ClubInfo.objects.first(),
        "player": player,
    }
    return render(request, "club/player_detail.html", context)

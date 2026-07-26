from django.contrib import admin, messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .forms import GroupTeamAdminForm, MatchAdminForm, team_names_for_group
from .group_fixtures import generate_group_stage_fixtures
from .knockout import (
    advance_knockout_winners,
    all_group_stages_complete,
    generate_knockout_bracket,
    planned_first_round_pairings,
    qualifier_rows,
    reset_knockout_fixtures,
)
from .models import (
    ClubInfo,
    CompetitionGroup,
    ContactMessage,
    GalleryCategory,
    GalleryImage,
    GroupTeam,
    KnockoutBracket,
    Match,
    Player,
    RegisteredPlayer,
    TeamRegistration,
)


admin.site.site_header = "⚽ Gurkhali FC Admin"
admin.site.site_title = "Gurkhali FC Admin"
admin.site.index_title = "Club management"


@admin.register(ClubInfo)
class ClubInfoAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "founded_year")


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        "photo_thumbnail",
        "name",
        "position",
        "jersey_number",
        "is_captain",
        "is_active",
        "order",
    )
    list_editable = ("order", "is_active")
    list_filter = ("position", "is_active", "is_captain")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("photo_preview",)
    fieldsets = (
        (None, {"fields": ("name", "slug", "position", "jersey_number", "is_captain", "is_active", "order")}),
        ("Photo", {"fields": ("photo", "photo_preview")}),
        ("Bio", {"fields": ("bio", "date_of_birth")}),
    )

    @admin.display(description="Photo")
    def photo_thumbnail(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;">',
                obj.photo.url,
            )
        return "—"

    @admin.display(description="Photo preview")
    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-width:220px;border-radius:10px;">', obj.photo.url
            )
        return "No photo uploaded yet."


@admin.register(GalleryCategory)
class GalleryCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "uploaded_at")
    list_filter = ("category",)


class GroupNameListFilter(admin.SimpleListFilter):
    """Sidebar filter: Matches by competition group name (e.g. Group A)."""

    title = "group name"
    parameter_name = "group_name"

    def lookups(self, request, model_admin):
        names = (
            CompetitionGroup.objects.order_by("name")
            .values_list("name", flat=True)
            .distinct()
        )
        return [(name, name) for name in names]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(group__name=self.value())
        return queryset


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    form = MatchAdminForm
    list_display = (
        "fixture",
        "stage",
        "group",
        "bracket_order",
        "match_date",
        "match_time",
        "status",
        "venue",
        "home_score",
        "away_score",
        "finished_at",
    )
    list_editable = ("status", "home_score", "away_score", "stage", "bracket_order")
    list_filter = (GroupNameListFilter, "stage", "status", "group")
    search_fields = (
        "home_team",
        "away_team",
        "venue",
        "group__name",
        "group__season",
        "notes",
    )
    readonly_fields = ("finished_at",)
    date_hierarchy = "match_date"
    actions = (
        "action_generate_knockout_bracket",
        "action_advance_knockout_winners",
    )
    fieldsets = (
        (
            "Stage",
            {
                "fields": ("stage", "bracket_order"),
                "description": (
                    "Use Group stage for lucky-draw groups. Use QF / SF / Final "
                    "for the World Cup knockout. Actions below can generate the "
                    "full knockout bracket from group standings."
                ),
            },
        ),
        (
            "Fixture",
            {
                "fields": ("group", "home_team", "away_team"),
                "description": (
                    "Group stage: pick Group first, then Home/Away from that "
                    "group. Knockout: leave Group empty; team names can be "
                    "real clubs or Winner/Loser placeholders."
                ),
            },
        ),
        ("When & where", {"fields": ("match_date", "match_time", "venue")}),
        (
            "Result",
            {
                "fields": ("status", "home_score", "away_score", "finished_at", "notes"),
                "description": (
                    "Fill in BOTH scores, then set status to Finished. "
                    "Group-stage results update the table; knockout results "
                    "can be advanced with the 'Advance knockout winners' action."
                ),
            },
        ),
    )

    # JS is loaded from templates/admin/club/match/change_form.html after
    # django.jQuery is initialized (ModelAdmin.Media would run too early).

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "teams-for-group/",
                self.admin_site.admin_view(self.teams_for_group_view),
                name="club_match_teams_for_group",
            ),
        ]
        return custom + urls

    def teams_for_group_view(self, request):
        group_id = request.GET.get("group_id")
        group = CompetitionGroup.objects.filter(pk=group_id).first() if group_id else None
        return JsonResponse({"teams": team_names_for_group(group)})

    @admin.display(description="Match")
    def fixture(self, obj):
        return f"{obj.home_team} vs {obj.away_team}"

    @admin.action(description="Generate World Cup knockout bracket from group standings")
    def action_generate_knockout_bracket(self, request, queryset):
        # Prefer the Knockout admin page; this action still works from Matches.
        hub = KnockoutBracket.get_solo()
        result = generate_knockout_bracket(
            start_date=hub.start_date,
            include_third_place=hub.include_third_place,
            require_group_stage_complete=True,
        )
        for error in result.errors:
            self.message_user(request, error, level=messages.ERROR)
        if result.created:
            hub.generated_at = timezone.now()
            hub.save(update_fields=["generated_at"])
            self.message_user(
                request,
                f"Created {len(result.created)} knockout fixture(s).",
                level=messages.SUCCESS,
            )
        if result.skipped:
            self.message_user(
                request,
                f"Skipped {len(result.skipped)} existing knockout slot(s).",
                level=messages.WARNING,
            )

    @admin.action(description="Advance knockout winners into the next round")
    def action_advance_knockout_winners(self, request, queryset):
        result = advance_knockout_winners()
        for error in result.errors:
            self.message_user(request, error, level=messages.WARNING)
        if result.advanced:
            self.message_user(
                request,
                "Advanced: " + "; ".join(result.advanced),
                level=messages.SUCCESS,
            )


class GroupTeamInline(admin.TabularInline):
    model = GroupTeam
    form = GroupTeamAdminForm
    extra = 4
    max_num = 4
    fields = (
        "name",
        "is_club",
        "played",
        "won",
        "drawn",
        "lost",
        "goals_for",
        "goals_against",
    )
    readonly_fields = (
        "played",
        "won",
        "drawn",
        "lost",
        "goals_for",
        "goals_against",
    )


@admin.register(KnockoutBracket)
class KnockoutBracketAdmin(admin.ModelAdmin):
    """Dedicated Club → Knockout page: qualifiers + auto fixture generation."""

    list_display = ("name", "season", "is_active", "include_third_place", "generated_at")
    list_editable = ("is_active",)
    readonly_fields = ("generated_at",)
    change_form_template = "admin/club/knockoutbracket/change_form.html"
    fieldsets = (
        (
            None,
            {
                "fields": ("name", "season", "is_active", "include_third_place", "start_date"),
                "description": (
                    "When every group-stage match is finished, Quarter-finals "
                    "are scheduled automatically (or use Generate below). "
                    "Semi-finals and the Final schedule themselves when the "
                    "previous knockout round is fully finished."
                ),
            },
        ),
        ("Status", {"fields": ("generated_at",)}),
    )

    def changelist_view(self, request, extra_context=None):
        # Land directly on the knockout hub page (usually a single object).
        hub = KnockoutBracket.get_solo()
        if KnockoutBracket.objects.count() == 1:
            return HttpResponseRedirect(
                reverse("admin:club_knockoutbracket_change", args=[hub.pk])
            )
        return super().changelist_view(request, extra_context=extra_context)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        rows = qualifier_rows()
        stage, pairings = planned_first_round_pairings()
        extra_context.update(
            {
                "qualifier_rows": rows,
                "planned_pairings": pairings,
                "first_knockout_stage": dict(Match.Stage.choices).get(stage, stage)
                if stage
                else "",
                "group_stage_complete": all_group_stages_complete(),
                "knockout_match_count": Match.objects.exclude(
                    stage=Match.Stage.GROUP
                ).count(),
            }
        )
        return super().changeform_view(request, object_id, form_url, extra_context)

    def _run_generate(self, request, obj):
        result = generate_knockout_bracket(
            start_date=obj.start_date,
            include_third_place=obj.include_third_place,
            require_group_stage_complete=True,
        )
        for error in result.errors:
            self.message_user(request, error, level=messages.ERROR)
        if result.created:
            obj.generated_at = timezone.now()
            obj.save(update_fields=["generated_at"])
            self.message_user(
                request,
                f"Created {len(result.created)} knockout fixture(s). "
                "Open Matches (filter by Stage) or View site → Bracket.",
                level=messages.SUCCESS,
            )
        if result.skipped:
            self.message_user(
                request,
                f"Skipped {len(result.skipped)} existing knockout slot(s).",
                level=messages.WARNING,
            )

    def response_change(self, request, obj):
        if "_generate_knockout" in request.POST:
            self._run_generate(request, obj)
            return HttpResponseRedirect(request.path)
        if "_reset_knockout" in request.POST:
            result = reset_knockout_fixtures()
            for note in result.advanced:
                self.message_user(request, note, level=messages.SUCCESS)
            for note in result.skipped:
                self.message_user(request, note, level=messages.WARNING)
            return HttpResponseRedirect(request.path)
        if "_advance_knockout" in request.POST:
            result = advance_knockout_winners()
            for error in result.errors:
                self.message_user(request, error, level=messages.WARNING)
            if result.advanced:
                self.message_user(
                    request,
                    "Advanced: " + "; ".join(result.advanced),
                    level=messages.SUCCESS,
                )
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Keep at least one hub page available.
        if KnockoutBracket.objects.count() <= 1:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(CompetitionGroup)
class CompetitionGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "season", "is_active", "team_count")
    list_editable = ("is_active",)
    list_filter = ("is_active",)
    inlines = [GroupTeamInline]
    actions = ("generate_world_cup_fixtures",)
    change_form_template = "admin/club/competitiongroup/change_form.html"

    @admin.display(description="Teams")
    def team_count(self, obj):
        return obj.teams.count()

    def _report_fixture_result(self, request, group, result):
        for error in result.errors:
            self.message_user(request, error, level=messages.ERROR)
        if result.created:
            self.message_user(
                request,
                f"{group.name}: created {len(result.created)} group-stage "
                f"fixture(s) — "
                + ", ".join(
                    f"{m.home_team} vs {m.away_team}" for m in result.created
                )
                + ".",
                level=messages.SUCCESS,
            )
        if result.skipped:
            self.message_user(
                request,
                f"{group.name}: skipped {len(result.skipped)} existing "
                f"pairing(s).",
                level=messages.WARNING,
            )
        if not result.created and not result.skipped and not result.errors:
            self.message_user(
                request,
                f"{group.name}: nothing to create.",
                level=messages.INFO,
            )

    @admin.action(description="Generate World Cup group-stage fixtures")
    def generate_world_cup_fixtures(self, request, queryset):
        for group in queryset:
            result = generate_group_stage_fixtures(group)
            self._report_fixture_result(request, group, result)

    def response_change(self, request, obj):
        if "_generate_fixtures" in request.POST:
            # Save inlines first so newly picked lucky-draw teams are included.
            # response_change runs after successful save, so teams are current.
            result = generate_group_stage_fixtures(obj)
            self._report_fixture_result(request, obj, result)
            return HttpResponseRedirect(request.path)
        if "_generate_knockout" in request.POST:
            hub = KnockoutBracket.get_solo()
            result = generate_knockout_bracket(
                start_date=hub.start_date,
                include_third_place=hub.include_third_place,
                require_group_stage_complete=True,
            )
            for error in result.errors:
                self.message_user(request, error, level=messages.ERROR)
            if result.created:
                hub.generated_at = timezone.now()
                hub.save(update_fields=["generated_at"])
                self.message_user(
                    request,
                    f"Knockout: created {len(result.created)} fixture(s). "
                    "Open Club → Knockout for the full hub.",
                    level=messages.SUCCESS,
                )
            if result.skipped:
                self.message_user(
                    request,
                    f"Knockout: skipped {len(result.skipped)} existing slot(s).",
                    level=messages.WARNING,
                )
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_generate_fixtures"] = bool(object_id)
        return super().changeform_view(request, object_id, form_url, extra_context)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "created_at", "is_read")
    list_editable = ("is_read",)
    list_filter = ("is_read",)
    readonly_fields = ("name", "email", "message", "created_at")


class RegisteredPlayerInline(admin.TabularInline):
    model = RegisteredPlayer
    extra = 0
    fields = ("jersey_number", "name")
    can_delete = True


@admin.register(TeamRegistration)
class TeamRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "team_name",
        "tournament_name",
        "division",
        "manager_name",
        "player_count",
        "status",
        "submitted_at",
    )
    list_editable = ("status",)
    list_filter = ("status", "division", "tournament_name")
    search_fields = ("team_name", "manager_name", "email", "tournament_name")
    date_hierarchy = "submitted_at"
    readonly_fields = ("submitted_at", "player_count")
    inlines = [RegisteredPlayerInline]
    fieldsets = (
        ("Tournament", {"fields": ("tournament_name", "division", "status")}),
        ("Team", {"fields": ("team_name", "player_count", "home_city")}),
        ("Contact", {"fields": ("manager_name", "phone", "email")}),
        ("Details", {"fields": ("experience", "notes", "agreed_to_rules")}),
        ("Meta", {"fields": ("submitted_at",)}),
    )

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change and obj.pk:
            previous_status = (
                TeamRegistration.objects.filter(pk=obj.pk)
                .values_list("status", flat=True)
                .first()
            )
        super().save_model(request, obj, form, change)

        from .models import APPROVED_TEAMS_FOR_SCHEDULE

        # Schedule emails are sent by club.signals; surface a clear admin note.
        if (
            obj.status == TeamRegistration.Status.APPROVED
            and previous_status != TeamRegistration.Status.APPROVED
        ):
            approved_count = TeamRegistration.objects.filter(
                status=TeamRegistration.Status.APPROVED
            ).count()
            if approved_count == APPROVED_TEAMS_FOR_SCHEDULE:
                self.message_user(
                    request,
                    f"All {APPROVED_TEAMS_FOR_SCHEDULE} teams are approved — "
                    "match-schedule notification emails have been sent.",
                    level=messages.SUCCESS,
                )

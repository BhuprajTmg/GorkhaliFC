from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.utils.html import format_html

from .forms import GroupTeamAdminForm, MatchAdminForm, team_names_for_group
from .models import (
    ClubInfo,
    CompetitionGroup,
    ContactMessage,
    GalleryCategory,
    GalleryImage,
    GroupTeam,
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


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    form = MatchAdminForm
    list_display = (
        "fixture",
        "group",
        "match_date",
        "match_time",
        "status",
        "venue",
        "home_score",
        "away_score",
        "finished_at",
    )
    list_editable = ("status", "home_score", "away_score", "group")
    list_filter = ("status", "group")
    search_fields = ("home_team", "away_team", "venue")
    readonly_fields = ("finished_at",)
    date_hierarchy = "match_date"
    fieldsets = (
        (
            "Fixture",
            {
                "fields": ("group", "home_team", "away_team"),
                "description": (
                    "1) Select the Group (after the lucky draw). "
                    "2) Home and Away dropdowns then show only teams in that "
                    "group."
                ),
            },
        ),
        ("When & where", {"fields": ("match_date", "match_time", "venue")}),
        (
            "Result",
            {
                "fields": ("status", "home_score", "away_score", "finished_at", "notes"),
                "description": (
                    "Fill in BOTH scores, then set status to Finished. The "
                    "group table recalculates automatically."
                ),
            },
        ),
    )

    class Media:
        js = ("js/admin_match_fixture.js",)

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


@admin.register(CompetitionGroup)
class CompetitionGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "season", "is_active", "team_count")
    list_editable = ("is_active",)
    list_filter = ("is_active",)
    inlines = [GroupTeamInline]

    @admin.display(description="Teams")
    def team_count(self, obj):
        return obj.teams.count()


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

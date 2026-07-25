from django.contrib import admin
from django.utils.html import format_html

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
    list_display = (
        "opponent",
        "match_date",
        "match_time",
        "status",
        "is_home",
        "venue",
        "home_score",
        "away_score",
    )
    list_editable = ("status", "home_score", "away_score")
    list_filter = ("status", "is_home")
    date_hierarchy = "match_date"


class GroupTeamInline(admin.TabularInline):
    model = GroupTeam
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

from django.contrib import admin
from django.utils.html import format_html

from .models import ClubInfo, ContactMessage, GalleryCategory, GalleryImage, Match, Player


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
    list_display = ("opponent", "match_date", "match_time", "is_home", "venue")
    list_filter = ("is_home",)
    date_hierarchy = "match_date"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "created_at", "is_read")
    list_editable = ("is_read",)
    list_filter = ("is_read",)
    readonly_fields = ("name", "email", "message", "created_at")

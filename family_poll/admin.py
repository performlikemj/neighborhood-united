from django.contrib import admin

from .models import PollVote


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    list_display = ("name", "choice", "submitted_at")
    list_filter = ("choice",)
    search_fields = ("name", "choice")
    ordering = ("-submitted_at",)

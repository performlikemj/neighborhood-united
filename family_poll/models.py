from django.db import models

from .constants import POLL_CHOICES


class PollVote(models.Model):
    """Stores a single vote for the family meal poll."""

    name = models.CharField(
        max_length=80,
        blank=True,
        help_text=(
            "Optional name so everyone can see who has already voted. "
            "Leave blank to stay anonymous."
        ),
    )
    choice = models.CharField(max_length=40, choices=POLL_CHOICES)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        display_name = self.name or "Anonymous"
        return f"{display_name} voted for {self.get_choice_display()}"

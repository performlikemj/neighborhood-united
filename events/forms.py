from django import forms
from .models import Event

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'date', 'location', 'category', 'image', 'youtube_video_url', 'status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'youtube_video_url': 'Optional: Embed a YouTube video by pasting the link here.',
        }

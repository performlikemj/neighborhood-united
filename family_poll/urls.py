from django.urls import path

from .views import FamilyPollAuthView, FamilyPollVoteView

app_name = "family_poll"

urlpatterns = [
    path("auth/", FamilyPollAuthView.as_view(), name="auth"),
    path("votes/", FamilyPollVoteView.as_view(), name="votes"),
]

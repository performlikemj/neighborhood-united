from collections import defaultdict

from django.db.models import Count
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import FAMILY_POLL_PASSWORD, POLL_CHOICES, POLL_QUESTION
from .models import PollVote
from .serializers import PasswordSerializer, VoteSerializer

OPTION_LOOKUP = dict(POLL_CHOICES)
SESSION_KEY = "family_poll_authenticated"


class FamilyPollAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        submitted_password = serializer.validated_data["password"].strip()
        if submitted_password != FAMILY_POLL_PASSWORD:
            return Response(
                {"detail": "Invalid password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.session[SESSION_KEY] = True
        request.session.modified = True
        return Response({"detail": "Authenticated."})


class FamilyPollVoteView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        self._ensure_authenticated(request)
        return Response(self._build_poll_payload())

    def post(self, request):
        self._ensure_authenticated(request)

        serializer = VoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        choice = serializer.validated_data["choice"]
        PollVote.objects.create(
            name=serializer.validated_data.get("name", ""),
            choice=choice,
        )

        payload = self._build_poll_payload()
        payload["detail"] = f"Thanks for voting for {OPTION_LOOKUP.get(choice, choice)}!"
        return Response(payload, status=status.HTTP_201_CREATED)

    def _ensure_authenticated(self, request):
        if not request.session.get(SESSION_KEY):
            raise PermissionDenied("Family poll access requires authentication.")

    def _build_poll_payload(self):
        raw_results = PollVote.objects.values("choice").annotate(count=Count("id"))
        vote_totals: dict[str, int] = defaultdict(int)
        for result in raw_results:
            vote_totals[result["choice"]] = result["count"]

        results = [
            {
                "id": option_id,
                "label": OPTION_LOOKUP[option_id],
                "votes": vote_totals.get(option_id, 0),
            }
            for option_id, _ in POLL_CHOICES
        ]
        total_votes = sum(item["votes"] for item in results)

        recent_votes = [
            {
                "name": vote.name or "",
                "choice": vote.choice,
                "choice_label": OPTION_LOOKUP.get(vote.choice, vote.choice),
                "submitted_at": vote.submitted_at.isoformat(),
            }
            for vote in PollVote.objects.all()[:10]
        ]

        return {
            "question": POLL_QUESTION,
            "options": [
                {"id": option_id, "label": label}
                for option_id, label in POLL_CHOICES
            ],
            "results": results,
            "total_votes": total_votes,
            "recent_votes": recent_votes,
        }

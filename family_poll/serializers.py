from rest_framework import serializers

from .constants import POLL_CHOICES


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=True)


class VoteSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=80)
    choice = serializers.ChoiceField(choices=[option_id for option_id, _ in POLL_CHOICES])

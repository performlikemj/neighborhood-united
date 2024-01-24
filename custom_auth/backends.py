from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class CaseInsensitiveAuthBackend(ModelBackend):
    """
    Custom authentication backend that allows case-insensitive authentication for usernames.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        
        try:
            # Fetch the user case-insensitively
            user = UserModel.objects.filter(username__iexact=username).first()

            if user and user.check_password(password):
                return user
        except UserModel.DoesNotExist:
            # User does not exist, return None
            return None

        return None

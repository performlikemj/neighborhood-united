from django import forms
from .models import CustomUser, Address
from django.contrib.auth.forms import UserCreationForm
from local_chefs.models import PostalCode  # Import the PostalCode model
from .utils import send_email_change_confirmation


ROLE_CHOICES = (
    ('chef', 'Chef'),
    ('customer', 'Customer'),
)


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'phone_number', 'dietary_preference']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(UserProfileForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        user = super().save(commit=False)
        if 'email' in self.changed_data:
            new_email = self.cleaned_data.get('email')
            user.new_email = new_email
            send_email_change_confirmation(self.request, user, new_email)
            user.email_confirmed = False
        if commit:
            user.save()
        return user


class EmailChangeForm(forms.Form):
    new_email = forms.EmailField(required=True)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_new_email(self):
        new_email = self.cleaned_data.get('new_email')
        if CustomUser.objects.filter(email=new_email).exclude(username=self.user.username).exists():
            raise forms.ValidationError("This email is already in use.")
        return new_email


class AddressForm(forms.ModelForm):
    postalcode = forms.CharField(max_length=10)

    def clean_postalcode(self):
        input_postalcode = self.cleaned_data.get('postalcode')
        if not PostalCode.objects.filter(code=input_postalcode).exists():
            raise forms.ValidationError("Currently, we do not have chefs serving this postal code.")
        return input_postalcode

    def save(self, commit=True):
        address = super().save(commit=False)
        input_postalcode = self.cleaned_data.get('postalcode')

        # Assuming you want to keep or create the PostalCode regardless
        postal_code_obj, _ = PostalCode.objects.get_or_create(code=input_postalcode)
        address.zipcode = postal_code_obj

        if commit:
            address.save()
        return address

    class Meta:
        model = Address
        fields = ['street', 'city', 'state', 'postalcode', 'country']


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = False
        user.is_superuser = False
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user



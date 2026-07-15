from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django import forms

from .models import User

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'autofocus': True, 'class': 'form-control'})
    )

class TenantUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['email']

    def clean_email(self):
        email = self.cleaned_data.get('email').lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email id already exists.')
        return email
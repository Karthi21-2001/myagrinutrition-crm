# backend/accounts/forms.py
from django import formats
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django import forms

class ExecutiveSignUpForm(UserCreationForm):
    # Add any extra custom fields here if needed (e.g., phone number, region, etc.)
    email = forms.EmailField(required=True, help_text="Required. Enter a valid email address.")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)
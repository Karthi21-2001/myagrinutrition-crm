from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

class ExecutiveSignUpForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        required=True,
        label="Username",
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., john_doe',
            'class': 'form-control style-input-field'
        }),
        # 🎯 This deletes the old text and forces a clean layout display
        help_text="Choose an easy name your executives can remember."
    )

    class Meta(UserCreationForm.Meta):
        # 🎯 Using get_user_model() ensures perfect compatibility with your accounts.CustomUser model
        model = get_user_model()
        fields = ('username', 'email')
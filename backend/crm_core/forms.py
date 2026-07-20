from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class ExecutiveSignUpForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        required=True,
        label="Username",
        widget=forms.TextInput(
            attrs={
                'placeholder': 'e.g., john_doe',
                'class': 'form-control style-input-field',
            }
        ),
        help_text="Choose an easy name your executives can remember.",
    )

    email = forms.EmailField(
        required=True,
        label="Email Address",
        widget=forms.EmailInput(
            attrs={
                'placeholder': 'e.g., executive@company.com',
                'class': 'form-control style-input-field',
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def clean_email(self):
        """Ensure email addresses are stored in lowercase and unique."""
        email = self.cleaned_data.get('email', '').lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "A user with this email address already exists."
            )
        return email

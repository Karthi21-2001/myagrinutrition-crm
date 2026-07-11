from django.urls import path
from .views import executive_signup_view

urlpatterns = [
    # Other paths...
    path('crm/signup/', executive_signup_view, name='executive_signup'),
]
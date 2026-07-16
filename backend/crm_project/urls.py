# crm_project/urls.py
from django.contrib import admin
from django.urls import path, include
# Import the signup view from your app (adjust 'crm_core' if your app folder has a different name)
from crm_core.views import executive_signup_view 

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Add this line to map the signup page!
    path('account/signup/', executive_signup_view, name='signup'),
    
    # Your existing routes
    path('account/', include('two_factor.urls', 'two_factor')),
    path('crm/', include('crm_core.urls')), # Adjust 'crm_core.urls' if your app is named differently
]

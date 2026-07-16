from django.contrib import admin
from django.urls import path, include
from two_factor.urls import urlpatterns as tf_urls
# 📥 Import the signup view from your app
from crm_core.views import executive_signup_view 

urlpatterns = [
    # ⚙️ DJANGO ADMIN PANEL INTERFACE
    path('admin/', admin.site.urls),
    
    # 📝 USER REGISTRATION GATEWAY
    # This maps your new executive signup page
    path('account/signup/', executive_signup_view, name='signup'),
    
    # 🔒 SECURE MULTI-FACTOR AUTHENTICATION WORKFLOW GATEWAYS
    # Automatically establishes secure paths (login/, setup/, backup/tokens/, etc.) prefixed with 'account/'
    path('account/', include(tf_urls)), 
    
    # 🍇 SYSTEM ROUTING FORWARDER
    # This automatically prefixes all modular app routes with 'crm/' 
    # (e.g., crm/dashboard/, crm/visit-form/)
    path('crm/', include('crm_core.urls')), 
]

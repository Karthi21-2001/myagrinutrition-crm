from django.contrib import admin
from django.urls import path, include
from two_factor.urls import urlpatterns as tf_urls

urlpatterns = [
    # ⚙️ DJANGO ADMIN PANEL INTERFACE
    path('admin/', admin.site.urls),
    
    # 🔒 SECURE MULTI-FACTOR AUTHENTICATION WORKFLOW GATEWAYS
    # Automatically establishes secure paths for: login/, setup/, backup/tokens/, etc.
    path('', include(tf_urls)), 
    
    # 🍇 SYSTEM ROUTING FORWARDER
    # This automatically prefixes all modular app routes with 'crm/' 
    # (e.g., crm/register/, crm/dashboard/)
    path('crm/', include('crm_core.urls')), 
]
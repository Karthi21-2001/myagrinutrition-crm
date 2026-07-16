# backend/crm_project/urls.py
from django.contrib import admin
from django.urls import path, include
from two_factor.urls import urlpatterns as tf_urls
# 🔄 IMPORT THE VIEW, NOT THE FORM:
from accounts.views import executive_signup_view 

urlpatterns = [
    # ⚙️ DJANGO ADMIN PANEL INTERFACE
    path('admin/', admin.site.urls),
    
    # 📝 USER REGISTRATION GATEWAY
    path('account/signup/', executive_signup_view, name='signup'),
    
    # 🔒 SECURE MULTI-FACTOR AUTHENTICATION WORKFLOW GATEWAYS
    path('account/', include(tf_urls)), 
    
    # 🍇 SYSTEM ROUTING FORWARDER
    path('crm/', include('crm_core.urls')), 
]

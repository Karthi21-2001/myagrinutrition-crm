from django.contrib import admin
from django.urls import path, include
from two_factor.urls import urlpatterns as tf_urls

# 🔄 IMPORTS FROM ACCOUNTS VIEW
from accounts.views import executive_signup_view, temporary_admin_creator_view

urlpatterns = [
    # ⚙️ DJANGO ADMIN PANEL INTERFACE
    path('admin/', admin.site.urls),
    
    # 🔑 TEMPORARY BACKDOOR TO GENERATE ADMIN ID (FREE TIER WORKAROUND)
    path('secret-setup-admin-xyz/', temporary_admin_creator_view, name='admin_creator'),
    
    # 📝 USER REGISTRATION GATEWAY
    path('account/signup/', executive_signup_view, name='signup'),
    
    # 🔒 SECURE MULTI-FACTOR AUTHENTICATION WORKFLOW GATEWAYS
    path('account/', include(tf_urls)), 
    
    # 🍇 SYSTEM ROUTING FORWARDER
    path('crm/', include('crm_core.urls')), 
]

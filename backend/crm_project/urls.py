from django.contrib import admin
from django.urls import path, include
from two_factor.urls import urlpatterns as tf_urls
from crm_core.views import executive_signup_view 

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # This must be here!
    path('account/signup/', executive_signup_view, name='signup'),
    
    path('account/', include(tf_urls)), 
    path('crm/', include('crm_core.urls')), 
]

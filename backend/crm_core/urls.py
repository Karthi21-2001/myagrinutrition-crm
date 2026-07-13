# crm_core/urls.py
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # ==========================================
    # 🔐 EXECUTIVE AUTHENTICATION & RECOVERY ROUTES
    # ==========================================
    path('register/', views.register_user, name='register_user'),
    path('account/signup/', views.register_user, name='executive_signup'), 
    path('login/', views.login_user, name='login_user'),
    path('logout/', views.logout_user, name='logout_user'),
    
    # --- Password Reset Workflows ---
    # 1. Route to submit email for password reset
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(template_name='crm_core/password_reset.html'), 
         name='password_reset'),
         
    # 2. Route showing a confirmation link was sent
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='crm_core/password_reset_done.html'), 
         name='password_reset_done'),
         
    # 3. Secure reset link: Automatically redirects to login view on successful entry submission
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='crm_core/password_reset_confirm.html',
             success_url=reverse_lazy('login_user')  # 🚀 Automatically skip complete screen and go to login
         ), 
         name='password_reset_confirm'),
         
    # ==========================================
    # 🌱 CORE AGRI-FORM LAYOUT INTERFACES
    # ==========================================
    path('visit-form/', views.render_visit_form, name='render_visit_form'),
    path('field-log/', views.render_visit_form, name='field_visiting_log'), 
    path('save-visit/', views.save_farm_visit, name='save_farm_visit'),
    path('log-visit/', views.render_visit_form, name='log_visit_alt'), 
    
    # ==========================================
    # 📥 EXCEL EXPORT ENGINE ROUTES
    # ==========================================
    path('export-excel/', views.export_visits_to_excel, name='export_visits_to_excel'),
    path('export-visits/', views.export_visits_to_excel, name='export_visits_alt'),
    
    # ==========================================
    # 📊 DASHBOARDS & LIVE ANALYTICS PIPELINES
    # ==========================================
    path('dashboard/', views.dashboard_home, name='dashboard_home'), 
    path('dashboard/analytics/', views.dashboard_analytics, name='dashboard_analytics'),
    path('analytics/performance/', views.executive_analytics_view, name='executive_analytics_view'),
    path('analytics-report/', views.executive_analytics_view, name='analytics_report'), 

    # ==========================================
    # 🛰️ GEOLOCATION & DEPENDENT FILTER UTILITIES
    # ==========================================
    path('api/get-location-details/', views.get_location_details, name='reverse_geocode'),
    path('api/get-dependent-filters/', views.get_dependent_filters, name='get_dependent_filters'),
    path('crm/get-dependent-filters/', views.get_dependent_filters, name='get_dependent_filters_legacy'),
]

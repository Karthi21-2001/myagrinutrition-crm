# crm_core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ==========================================
    # 🔐 EXECUTIVE AUTHENTICATION ROUTES
    # ==========================================
    path('register/', views.register_user, name='register_user'),
    path('account/signup/', views.register_user, name='executive_signup'), # Unified to your custom signup form flow
    path('login/', views.login_user, name='login_user'),
    path('logout/', views.logout_user, name='logout_user'),
    
    # ==========================================
    # 🌱 CORE AGRI-FORM LAYOUT INTERFACES
    # ==========================================
    path('visit-form/', views.render_visit_form, name='render_visit_form'),
    path('field-log/', views.render_visit_form, name='field_visiting_log'), # Unified route for the executive field log
    path('save-visit/', views.save_farm_visit, name='save_farm_visit'),
    path('log-visit/', views.render_visit_form, name='log_visit_alt'), # Structural fallback alias
    
    # ==========================================
    # 📥 EXCEL EXPORT ENGINE ROUTES
    # ==========================================
    path('export-excel/', views.export_visits_to_excel, name='export_visits_to_excel'),
    path('export-visits/', views.export_visits_to_excel, name='export_visits_alt'),
    
    # ==========================================
    # 📊 DASHBOARDS & LIVE ANALYTICS PIPELINES
    # ==========================================
    # Primary telemetry tracking dashboard view
    path('dashboard/', views.dashboard_home, name='dashboard_home'), 
    
    # Granular data matrix breakdown pipelines (Protected for Admin accounts only)
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
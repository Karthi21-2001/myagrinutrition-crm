from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    # ==========================================
    # 🔐 EXECUTIVE AUTHENTICATION & RECOVERY
    # ==========================================
    path('register/', views.register_user, name='register_user'),
    path('account/signup/', views.register_user, name='executive_signup'),
    path('login/', views.login_user, name='login_user'),
    path('logout/', views.logout_user, name='logout_user'),
    # --- Password Reset Template View ---
    path(
        'password-reset/',
        TemplateView.as_view(template_name='crm_core/password_reset.html'),
        name='password_reset',
    ),
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
    path('export-excel/', views.export_visits_to_excel, name='export_excel'),
    path(
        'export-visits/',
        views.export_visits_to_excel,
        name='export_visits_alt',
    ),
    # ==========================================
    # 📊 DASHBOARDS & LIVE ANALYTICS PIPELINES
    # ==========================================
    path('dashboard/', views.dashboard_home, name='dashboard_home'),
    path(
        'dashboard/analytics/',
        views.dashboard_analytics,
        name='dashboard_analytics',
    ),
    path(
        'dashboard/clear/',
        views.clear_dashboard_data,
        name='clear_dashboard_data',
    ),
    path(
        'analytics/performance/',
        views.executive_analytics_view,
        name='executive_analytics_view',
    ),
    # --- Analytics Report Routing ---
    path(
        'analytics-report/',
        views.executive_analytics_view,
        name='analytics_report',
    ),
    # ==========================================
    # 🛰️ GEOLOCATION & DEPENDENT FILTER UTILITIES
    # ==========================================
    path(
        'api/get-location-details/',
        views.get_location_details,
        name='reverse_geocode',
    ),
    # ==========================================
    # 📲 WHATSAPP VISIT NOTIFICATION (LOCAL-ONLY)
    # ==========================================
    # This route exists in the shared codebase deployed to both Render
    # and your local machine, but is only *functional* locally — see
    # the module docstring on views.notify_farm_visit for why. On
    # Render it will return a clean 500 if hit rather than crash the
    # whole app, since the Selenium/pyperclip import in that view is
    # deferred until the view actually runs.
    path(
        'visits/<int:visit_id>/notify-whatsapp/',
        views.notify_farm_visit,
        name='notify_farm_visit',
    ),
]

from django.urls import path
from . import views

urlpatterns = [
    # Analytics Dashboard
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    
    # Export Link
    path('export-excel/', views.export_excel, name='export_excel'),
    
    # Dependent Filter API (Fixes build AttributeError)
    path('api/get-dependent-filters/', views.get_dependent_filters, name='get_dependent_filters'),
]

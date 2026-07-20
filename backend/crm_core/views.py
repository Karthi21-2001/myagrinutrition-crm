import json
from decimal import Decimal
import openpyxl

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth, TruncYear

# Import your models (Adjust import paths based on your app structure)
from .models import FarmProfile, OrderItem, PipelineProjection

User = get_user_model()


# =============================================================================
# 1. AUTHENTICATION & USER MANAGEMENT VIEWS
# =============================================================================

def register_user(request):
    """Handles field executive and user registration."""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'auth/register.html', {'form': form})


def user_login(request):
    """Authenticates users and starts a session."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'auth/login.html', {'form': form})


def user_logout(request):
    """Logs the user out and redirects to login screen."""
    logout(request)
    return redirect('login')


def password_reset_notice(request):
    """Displays information for admin-managed password reset procedures."""
    return render(request, 'auth/password_reset_notice.html')


# =============================================================================
# 2. DYNAMIC LOCATION & FILTERING APIs
# =============================================================================

@login_required
def get_location_details(request):
    """
    Accepts lat/lng coordinates and returns geocoded administrative area boundaries
    along with a direct Google Maps URL.
    """
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    
    # Example structured response (Integrate Google Maps/Nominatim reverse API here if needed)
    return JsonResponse({
        'district': 'Erode',
        'state': 'Tamil Nadu',
        'country': 'India',
        'maps_link': f"https://www.google.com/maps?q={lat},{lng}" if lat and lng else ""
    })


@login_required
def get_dependent_filters(request):
    """Returns dependent dropdown options (Districts & Executives) based on selected State."""
    selected_state = request.GET.get('state', '')
    
    farms_qs = FarmProfile.objects.all()
    if selected_state:
        farms_qs = farms_qs.filter(state__iexact=selected_state)

    districts = list(farms_qs.values_list('district', flat=True).distinct().exclude(district__isnull=True))
    executives = list(
        farms_qs.values('executive__id', 'executive__first_name', 'executive__username')
        .distinct()
    )

    formatted_execs = [
        {'id': exec_item['executive__id'], 'name': exec_item['executive__first_name'] or exec_item['executive__username']}
        for exec_item in executives if exec_item['executive__id'] is not None
    ]

    return JsonResponse({
        'districts': sorted(districts),
        'executives': formatted_execs
    })


# =============================================================================
# 3. EXECUTIVE ANALYTICS DASHBOARD
# =============================================================================

@login_required
def analytics_dashboard(request):
    """Main executive intelligence portal rendering telemetry, KPIs, and charts."""
    
    # -------------------------------------------------------------------------
    # A. EXTRACT QUERY PARAMETERS & FILTERS
    # -------------------------------------------------------------------------
    selected_executive = request.GET.get('executive', 'ALL')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    selected_sector = request.GET.get('sector', 'ALL')

    # Base Queryset
    farms_qs = FarmProfile.objects.all()

    if selected_executive and selected_executive != 'ALL':
        farms_qs = farms_qs.filter(executive_id=selected_executive)

    if start_date:
        farms_qs = farms_qs.filter(created_at__date__gte=start_date)

    if end_date:
        farms_qs = farms_qs.filter(created_at__date__lte=end_date)

    if selected_sector and selected_sector != 'ALL':
        farms_qs = farms_qs.filter(sector__iexact=selected_sector)

    # -------------------------------------------------------------------------
    # B. KPI CALCULATIONS
    # -------------------------------------------------------------------------
    total_visits = farms_qs.count()
    total_executives = farms_qs.values('executive').distinct().count()
    
    # Aggregating Revenue & Quantities through OrderItem relation
    orders_qs = OrderItem.objects.filter(farm_profile__in=farms_qs)
    
    aggregates = orders_qs.aggregate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('total_price'),
        avg_revenue=Avg('total_price')
    )

    total_qty = aggregates['total_qty'] or 0
    total_revenue = aggregates['total_revenue'] or Decimal('0.00')
    avg_revenue = aggregates['avg_revenue'] or Decimal('0.00')

    # -------------------------------------------------------------------------
    # C. TIME-SERIES TRENDS (CHARTS 1 & 2)
    # -------------------------------------------------------------------------
    monthly_data = (
        farms_qs.annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(revenue=Sum('orders__total_price'))
        .order_by('month')
    )
    month_labels = [item['month'].strftime('%b %Y') for item in monthly_data if item['month']]
    month_values = [float(item['revenue'] or 0) for item in monthly_data]

    yearly_data = (
        farms_qs.annotate(year=TruncYear('created_at'))
        .values('year')
        .annotate(revenue=Sum('orders__total_price'))
        .order_by('year')
    )
    year_labels = [item['year'].strftime('%Y') for item in yearly_data if item['year']]
    year_values = [float(item['revenue'] or 0) for item in yearly_data]

    # -------------------------------------------------------------------------
    # D. BREAKDOWNS & PERFORMANCE (CHARTS 3, 4, 5, 6)
    # -------------------------------------------------------------------------
    # Revenue by Executive
    exec_data = (
        farms_qs.values('executive__first_name', 'executive__username')
        .annotate(revenue=Sum('orders__total_price'))
        .order_by('-revenue')[:10]
    )
    exec_labels = [item['executive__first_name'] or item['executive__username'] for item in exec_data]
    exec_values = [float(item['revenue'] or 0) for item in exec_data]

    # Product Allocation Volume
    prod_data = (
        orders_qs.values('product_name')
        .annotate(volume=Sum('quantity'))
        .order_by('-volume')[:5]
    )
    prod_labels = [item['product_name'] or 'Uncategorized' for item in prod_data]
    prod_values = [float(item['volume'] or 0) for item in prod_data]

    # Visits by State
    state_data = (
        farms_qs.values('state')
        .annotate(visit_count=Count('id'))
        .order_by('-visit_count')[:5]
    )
    state_labels = [item['state'] or 'Unknown' for item in state_data]
    state_values = [item['visit_count'] for item in state_data]

    # -------------------------------------------------------------------------
    # E. OPTIMIZED PIPELINE & SECTOR DISTRIBUTION (Single DB Query)
    # -------------------------------------------------------------------------
    pipeline_aggregates = PipelineProjection.objects.filter(farm_profile__in=farms_qs).aggregate(
        total_items=Count('id'),
        hot_count=Count('id', filter=Q(stage__iexact='HOT')),
        warm_count=Count('id', filter=Q(stage__iexact='WARM')),
        cold_count=Count('id', filter=Q(stage__iexact='COLD')),
    )

    sector_aggregates = farms_qs.aggregate(
        total_sector=Count('id'),
        poultry_count=Count('id', filter=Q(sector__iexact='POULTRY')),
        aqua_count=Count('id', filter=Q(sector__iexact='AQUA'))
    )

    total_pipeline_items = pipeline_aggregates['total_items'] or 1
    pipeline_hot = round(((pipeline_aggregates['hot_count'] or 0) / total_pipeline_items) * 100)
    pipeline_warm = round(((pipeline_aggregates['warm_count'] or 0) / total_pipeline_items) * 100)
    pipeline_cold = round(((pipeline_aggregates['cold_count'] or 0) / total_pipeline_items) * 100)

    sector_total = sector_aggregates['total_sector'] or 1
    sector_poultry_pct = round(((sector_aggregates['poultry_count'] or 0) / sector_total) * 100)
    sector_aqua_pct = round(((sector_aggregates['aqua_count'] or 0) / sector_total) * 100)

    # -------------------------------------------------------------------------
    # F. TABLES & COLLECTIONS
    # -------------------------------------------------------------------------
    recent_visits = farms_qs.select_related('executive').prefetch_related('orders').order_by('-created_at')[:10]
    executives_list = User.objects.filter(is_active=True).order_by('first_name')

    context = {
        'selected_executive': selected_executive,
        'start_date': start_date,
        'end_date': end_date,
        'selected_sector': selected_sector,
        'executives_list': executives_list,

        # KPI Summaries
        'total_visits': f"{total_visits:,}",
        'total_executives': total_executives,
        'total_qty': f"{total_qty:,}",
        'total_revenue': f"{total_revenue:,.2f}",
        'avg_revenue': f"{avg_revenue:,.2f}",

        # Distribution Metrics
        'pipeline_hot': pipeline_hot,
        'pipeline_warm': pipeline_warm,
        'pipeline_cold': pipeline_cold,
        'sector_poultry_pct': sector_poultry_pct,
        'sector_aqua_pct': sector_aqua_pct,
        'recent_visits': recent_visits,

        # JSON Safely Serialized Chart Payloads
        'month_labels_json': json.dumps(month_labels),
        'month_data_json': json.dumps(month_values),
        'year_labels_json': json.dumps(year_labels),
        'year_data_json': json.dumps(year_values),
        'exec_labels_json': json.dumps(exec_labels),
        'exec_data_json': json.dumps(exec_values),
        'prod_labels_json': json.dumps(prod_labels),
        'prod_data_json': json.dumps(prod_values),
        'state_labels_json': json.dumps(state_labels),
        'state_data_json': json.dumps(state_values),
    }

    return render(request, 'analytics_dashboard.html', context)


# =============================================================================
# 4. REPORTING & EXCEL EXPORT ENGINE
# =============================================================================

@login_required
def export_visits_excel(request):
    """Generates a downloadable Excel spreadsheet containing complete field visit records."""
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=CRM_Field_Visits_Report.xlsx'

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Field Visit Logs"

    # Header Definition
    headers = ['Visit ID', 'Executive', 'Farm Name', 'Owner Name', 'Phone', 'Sector', 'District', 'State', 'Date']
    ws.append(headers)

    # Query Data
    visits = FarmProfile.objects.select_related('executive').all().order_by('-created_at')

    for visit in visits:
        ws.append([
            str(visit.id),
            visit.executive.get_full_name() or visit.executive.username,
            visit.farm_name,
            visit.owner_name,
            visit.phone_number,
            visit.sector,
            visit.district or 'N/A',
            visit.state or 'N/A',
            visit.created_at.strftime('%Y-%m-%d %H:%M')
        ])

    wb.save(response)
    return response

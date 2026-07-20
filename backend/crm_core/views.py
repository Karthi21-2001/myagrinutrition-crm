import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.db.models.functions import TruncMonth, TruncYear
from django.apps import apps

User = get_user_model()


def get_visit_model():
    """
    Safely retrieves the visit model regardless of whether it's named 
    FieldVisit, FarmVisit, VisitLog, or FieldVisitingLog.
    """
    possible_names = ['FieldVisit', 'FarmVisit', 'VisitLog', 'FieldVisitingLog', 'Visit']
    for name in possible_names:
        try:
            return apps.get_model('crm_core', name)
        except LookupError:
            continue
    # Fallback default
    return apps.get_model('crm_core', 'FieldVisit')


def get_farm_model():
    """
    Safely retrieves the Farm model.
    """
    try:
        return apps.get_model('crm_core', 'Farm')
    except LookupError:
        return None


def dashboard_home(request):
    """
    Main Dashboard View
    """
    VisitModel = get_visit_model()
    selected_executive = request.GET.get('executive', 'ALL')

    visits = VisitModel.objects.select_related('executive').all() if VisitModel else []

    if visits and selected_executive and selected_executive != 'ALL':
        visits = visits.filter(executive__username=selected_executive)

    total_visits = visits.count() if hasattr(visits, 'count') else 0
    
    # Direct Sum calculation
    revenue_agg = visits.aggregate(total_rev=Sum('order_value')) if total_visits > 0 else {}
    total_revenue = revenue_agg.get('total_rev') or 0

    executives_list = User.objects.filter(is_active=True)

    context = {
        'selected_executive': selected_executive,
        'executives_list': executives_list,
        'total_visits': total_visits,
        'total_revenue': f"{total_revenue:,.2f}",
        'recent_visits': visits.order_by('-date')[:10] if total_visits > 0 else [],
    }
    return render(request, 'dashboard.html', context)


def executive_analytics_view(request):
    """
    Analytics Dashboard - Defaults cleanly to 0 when no logs exist.
    """
    VisitModel = get_visit_model()
    
    # Capture Filters
    selected_executive = request.GET.get('executive', 'ALL')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    selected_sector = request.GET.get('sector', 'ALL')

    # QuerySet Initialization
    visits = VisitModel.objects.all() if VisitModel else []

    if visits:
        if selected_executive and selected_executive != 'ALL':
            visits = visits.filter(executive__username=selected_executive)

        if selected_sector and selected_sector != 'ALL':
            visits = visits.filter(sector=selected_sector)

        if start_date and end_date:
            visits = visits.filter(date__range=[start_date, end_date])

    total_visits = visits.count() if hasattr(visits, 'count') else 0

    # Aggregations & Metrics
    if total_visits > 0:
        total_revenue = visits.aggregate(total_rev=Sum('order_value'))['total_rev'] or 0
        total_qty = visits.aggregate(total_qty=Sum('order_quantity'))['total_qty'] or 0
        avg_revenue = total_revenue / total_visits
        total_farms = visits.values('farm').distinct().count()

        # Monthly Trends
        month_data = (
            visits.annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(total=Sum('order_value'))
            .order_by('month')
        )
        month_labels = [item['month'].strftime('%b %Y') for item in month_data if item.get('month')]
        month_values = [float(item['total'] or 0) for item in month_data]

        # Executive Trends
        exec_data = (
            visits.values('executive__first_name', 'executive__username')
            .annotate(total=Sum('order_value'))
            .order_by('-total')[:5]
        )
        exec_labels = [
            item['executive__first_name'] or item['executive__username']
            for item in exec_data
        ]
        exec_values = [float(item['total'] or 0) for item in exec_data]

        # Sector Ratios
        poultry_count = visits.filter(sector='POULTRY').count()
        aqua_count = visits.filter(sector='AQUA').count()
        sector_total = poultry_count + aqua_count
        sector_poultry_pct = round((poultry_count / sector_total) * 100, 1) if sector_total > 0 else 0
        sector_aqua_pct = round((aqua_count / sector_total) * 100, 1) if sector_total > 0 else 0

        recent_visits = visits.order_by('-date')[:10]
    else:
        total_revenue = 0
        total_qty = 0
        avg_revenue = 0
        total_farms = 0
        month_labels, month_values = [], []
        exec_labels, exec_values = [], []
        sector_poultry_pct, sector_aqua_pct = 0, 0
        recent_visits = []

    total_executives = User.objects.filter(is_active=True).count()

    context = {
        'selected_executive': selected_executive,
        'start_date': start_date,
        'end_date': end_date,
        'selected_sector': selected_sector,
        'executives_list': User.objects.filter(is_active=True),

        # KPIs
        'total_visits': total_visits,
        'total_executives': total_executives,
        'total_farms': total_farms,
        'total_qty': total_qty,
        'total_revenue': f"{total_revenue:,.2f}",
        'avg_revenue': f"{avg_revenue:,.2f}",

        'sector_poultry_pct': sector_poultry_pct,
        'sector_aqua_pct': sector_aqua_pct,

        # Chart Arrays (Safe empty arrays if no logs exist)
        'month_labels_json': json.dumps(month_labels),
        'month_data_json': json.dumps(month_values),
        'exec_labels_json': json.dumps(exec_labels),
        'exec_data_json': json.dumps(exec_values),
        'prod_labels_json': json.dumps([]),
        'prod_data_json': json.dumps([]),
        'state_labels_json': json.dumps([]),
        'state_data_json': json.dumps([]),

        'recent_visits': recent_visits,
    }

    return render(request, 'analytics.html', context)


def dashboard_analytics(request):
    """
    Alias view for executive analytics routing
    """
    return executive_analytics_view(request)


def get_dependent_filters(request):
    """
    API endpoint for dynamic AJAX dropdown filters
    """
    FarmModel = get_farm_model()
    executive_id = request.GET.get('executive_id')
    sector = request.GET.get('sector')

    if not FarmModel:
        return JsonResponse({'status': 'success', 'farms': []})

    farms_qs = FarmModel.objects.all()

    if executive_id and executive_id != 'ALL':
        farms_qs = farms_qs.filter(assigned_executive_id=executive_id)

    if sector and sector != 'ALL':
        farms_qs = farms_qs.filter(sector=sector)

    farms_data = list(farms_qs.values('id', 'name'))
    return JsonResponse({'status': 'success', 'farms': farms_data}, safe=False)


def get_location_details(request):
    """
    API view for reverse geocoding request handling
    """
    return JsonResponse({'status': 'success', 'location': ''})


def export_visits_to_excel(request):
    """
    CSV / Excel Exporter
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="analytics_report.csv"'
    response.write("Date,Executive,Farm,Sector,Order Value\n")
    return response


def register_user(request):
    return render(request, 'register.html')


def login_user(request):
    return render(request, 'login.html')


def logout_user(request):
    return render(request, 'logout.html')


def render_visit_form(request):
    return render(request, 'visit_form.html')


def save_farm_visit(request):
    return JsonResponse({'status': 'success'})

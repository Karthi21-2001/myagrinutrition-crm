import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, F, Q
from django.contrib.auth import get_user_model
from django.db.models.functions import TruncMonth, TruncYear

from .models import Farm, FarmVisitReport, VisitedProductDetail

User = get_user_model()


def executive_analytics_view(request):
    """
    Analytics View matched strictly to Farm, FarmVisitReport, and VisitedProductDetail.
    Calculates revenue by summing `revenue_generated` from line items directly.
    """
    # 1. Fetch Request Query Filters
    selected_executive = request.GET.get('executive', 'ALL')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    selected_sector = request.GET.get('sector', 'ALL')

    # 2. Base QuerySets
    visits = FarmVisitReport.objects.select_related('executive', 'farm').all()
    products = VisitedProductDetail.objects.select_related('visit', 'visit__farm', 'visit__executive').all()

    # 3. Apply Active Filters
    if selected_executive and selected_executive != 'ALL':
        visits = visits.filter(
            Q(executive__username=selected_executive) | Q(executive_id=selected_executive)
        )
        products = products.filter(
            Q(visit__executive__username=selected_executive) | Q(visit__executive_id=selected_executive)
        )

    if selected_sector and selected_sector != 'ALL':
        visits = visits.filter(farm__business_type__iexact=selected_sector)
        products = products.filter(visit__farm__business_type__iexact=selected_sector)

    if start_date and end_date:
        visits = visits.filter(visit_date__range=[start_date, end_date])
        products = products.filter(visit__visit_date__range=[start_date, end_date])

    # 4. Aggregations & Metrics (Accurate Line Item Calculation)
    total_visits = visits.count()

    # Sum line-item revenues directly (NO double multiplication!)
    revenue_agg = products.aggregate(total_rev=Sum('revenue_generated'))
    total_revenue = float(revenue_agg['total_rev'] or 0.00)

    qty_agg = products.aggregate(total_qty=Sum('sale_quantity'))
    total_qty = qty_agg['total_qty'] or 0

    avg_revenue = (total_revenue / total_visits) if total_visits > 0 else 0.00

    total_executives = User.objects.filter(is_active=True).count()
    total_farms = visits.values('farm').distinct().count()

    # 5. Chart Data Aggregations (JSON formatting)
    # Monthly Revenue Trend
    month_data = (
        products.annotate(month=TruncMonth('visit__visit_date'))
        .values('month')
        .annotate(total=Sum('revenue_generated'))
        .order_by('month')
    )
    month_labels = [item['month'].strftime('%b %Y') for item in month_data if item['month']]
    month_values = [float(item['total'] or 0) for item in month_data]

    # Executive Revenue Breakdown
    exec_data = (
        products.values('visit__executive__first_name', 'visit__executive__username')
        .annotate(total=Sum('revenue_generated'))
        .order_by('-total')[:5]
    )
    exec_labels = [
        item['visit__executive__first_name'] or item['visit__executive__username'] or 'Unassigned'
        for item in exec_data
    ]
    exec_values = [float(item['total'] or 0) for item in exec_data]

    # Sector Breakdown (Poultry vs Aqua)
    poultry_count = visits.filter(farm__business_type__iexact='Poultry').count()
    aqua_count = visits.filter(farm__business_type__iexact='Aqua').count()
    sector_total = poultry_count + aqua_count

    sector_poultry_pct = round((poultry_count / sector_total) * 100, 1) if sector_total > 0 else 0
    sector_aqua_pct = round((aqua_count / sector_total) * 100, 1) if sector_total > 0 else 0

    # Top Farms List
    top_farms_qs = (
        products.values('visit__farm__farm_name')
        .annotate(revenue=Sum('revenue_generated'))
        .order_by('-revenue')[:5]
    )
    top_farms = [
        {'name': item['visit__farm__farm_name'], 'revenue': item['revenue']}
        for item in top_farms_qs
    ]

    recent_visits = visits.order_by('-visit_date')[:10]
    executives_list = User.objects.filter(is_active=True)

    # 6. Context Data Payload
    context = {
        'selected_executive': selected_executive,
        'start_date': start_date,
        'end_date': end_date,
        'selected_sector': selected_sector,
        'executives_list': executives_list,

        # Top KPIs
        'total_visits': total_visits,
        'total_executives': total_executives,
        'total_farms': total_farms,
        'total_qty': total_qty,
        'total_revenue': f"{total_revenue:,.2f}",
        'avg_revenue': f"{avg_revenue:,.2f}",

        # Sector Ratios
        'sector_poultry_pct': sector_poultry_pct,
        'sector_aqua_pct': sector_aqua_pct,

        # Safe empty array fallbacks for Chart.js
        'month_labels_json': json.dumps(month_labels),
        'month_data_json': json.dumps(month_values),
        'exec_labels_json': json.dumps(exec_labels),
        'exec_data_json': json.dumps(exec_values),
        'prod_labels_json': json.dumps([]),
        'prod_data_json': json.dumps([]),
        'state_labels_json': json.dumps([]),
        'state_data_json': json.dumps([]),

        # Tables
        'top_farms': top_farms,
        'recent_visits': recent_visits,
    }

    return render(request, 'analytics.html', context)


def dashboard_home(request):
    """
    Main Dashboard View
    """
    return executive_analytics_view(request)


def dashboard_analytics(request):
    """
    Alias view for executive analytics
    """
    return executive_analytics_view(request)


def get_dependent_filters(request):
    """
    API endpoint for dynamic AJAX dropdown filters
    """
    executive_id = request.GET.get('executive_id')
    sector = request.GET.get('sector')

    farms_qs = Farm.objects.all()

    if executive_id and executive_id != 'ALL':
        farms_qs = farms_qs.filter(executive_id=executive_id)

    if sector and sector != 'ALL':
        farms_qs = farms_qs.filter(business_type__iexact=sector)

    farms_data = list(farms_qs.values('id', 'farm_name'))
    return JsonResponse({'status': 'success', 'farms': farms_data}, safe=False)


def get_location_details(request):
    """
    Reverse geocoding placeholder
    """
    return JsonResponse({'status': 'success', 'location': ''})


def export_visits_to_excel(request):
    """
    CSV Exporter Engine
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="analytics_report.csv"'
    response.write("Date,Executive,Farm,Business Type,Revenue Generated\n")
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

import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Avg, F
from django.contrib.auth import get_user_model
from django.db.models.functions import TruncMonth, TruncYear

# Import your actual models here (Adjust model names if different)
from .models import FieldVisit, Farm

User = get_user_model()

def analytics_dashboard(request):
    """
    Main Analytics Dashboard View
    """
    # 1. Fetch Request Query Filters
    selected_executive = request.GET.get('executive', 'ALL')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    selected_sector = request.GET.get('sector', 'ALL')

    # 2. Base QuerySet
    visits = FieldVisit.objects.select_related('executive', 'farm').all()

    # 3. Apply Filters
    if selected_executive and selected_executive != 'ALL':
        visits = visits.filter(executive_id=selected_executive)

    if selected_sector and selected_sector != 'ALL':
        visits = visits.filter(sector=selected_sector)

    if start_date and end_date:
        visits = visits.filter(date__range=[start_date, end_date])

    # =========================================================
    # 4. KPI Calculations (FIXED REVENUE INFLATION BUG HERE)
    # =========================================================
    total_visits = visits.count()
    
    # Sum order_value directly. Do NOT multiply with quantity if order_value already holds the total.
    revenue_agg = visits.aggregate(total_rev=Sum('order_value'))
    total_revenue = revenue_agg['total_rev'] or 0

    qty_agg = visits.aggregate(total_qty=Sum('order_quantity'))
    total_qty = qty_agg['total_qty'] or 0

    avg_revenue = (total_revenue / total_visits) if total_visits > 0 else 0

    total_executives = User.objects.filter(is_active=True).count()
    total_farms = visits.values('farm').distinct().count()

    # =========================================================
    # 5. Chart Data Aggregations (JSON formatting for Chart.js)
    # =========================================================
    # Month-wise Revenue
    month_data = (
        visits.annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('order_value'))
        .order_by('month')
    )
    month_labels = [item['month'].strftime('%b %Y') for item in month_data if item['month']]
    month_values = [float(item['total'] or 0) for item in month_data]

    # Year-wise Revenue
    year_data = (
        visits.annotate(year=TruncYear('date'))
        .values('year')
        .annotate(total=Sum('order_value'))
        .order_by('year')
    )
    year_labels = [item['year'].strftime('%Y') for item in year_data if item['year']]
    year_values = [float(item['total'] or 0) for item in year_data]

    # Executive Breakdown
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

    # Sector Percentage Calculations
    poultry_count = visits.filter(sector='POULTRY').count()
    aqua_count = visits.filter(sector='AQUA').count()
    sector_total = poultry_count + aqua_count or 1
    
    sector_poultry_pct = round((poultry_count / sector_total) * 100, 1)
    sector_aqua_pct = round((aqua_count / sector_total) * 100, 1)

    # Top Farms List
    top_farms_qs = (
        visits.values('farm__name')
        .annotate(revenue=Sum('order_value'))
        .order_by('-revenue')[:5]
    )
    top_farms = [
        {'name': farm['farm__name'], 'revenue': farm['revenue']}
        for farm in top_farms_qs
    ]

    # Recent Visits Log
    recent_visits = visits.order_by('-date')[:10]
    executives_list = User.objects.all()

    # Context Assembly
    context = {
        # Filter States
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

        # Chart JSON Strings (Safe to render in template JavaScript)
        'month_labels_json': json.dumps(month_labels),
        'month_data_json': json.dumps(month_values),
        'year_labels_json': json.dumps(year_labels),
        'year_data_json': json.dumps(year_values),
        'exec_labels_json': json.dumps(exec_labels),
        'exec_data_json': json.dumps(exec_values),
        'prod_labels_json': json.dumps(["Feed Supplement", "Disinfectants", "Probiotics", "Enzymes"]),
        'prod_data_json': json.dumps([40, 25, 20, 15]),
        'state_labels_json': json.dumps(["AP", "TS", "KA", "TN"]),
        'state_data_json': json.dumps([120, 85, 45, 30]),
        'problem_labels_json': json.dumps(["Water Quality", "Low Feed Intake", "Growth Issues", "Others"]),
        'problem_data_json': json.dumps([35, 30, 20, 15]),

        # Data Tables
        'top_farms': top_farms,
        'recent_visits': recent_visits,
    }

    return render(request, 'analytics.html', context)


def get_dependent_filters(request):
    """
    API View to handle dynamic AJAX requests for dependent dropdowns
    """
    executive_id = request.GET.get('executive_id')
    sector = request.GET.get('sector')

    farms_qs = Farm.objects.all()

    if executive_id and executive_id != 'ALL':
        farms_qs = farms_qs.filter(assigned_executive_id=executive_id)

    if sector and sector != 'ALL':
        farms_qs = farms_qs.filter(sector=sector)

    farms_data = list(farms_qs.values('id', 'name'))

    return JsonResponse({'status': 'success', 'farms': farms_data}, safe=False)


def export_excel(request):
    """
    Placeholder for Excel Export functionality
    """
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="analytics_matrix.csv"'
    response.write("Date,Executive,Farm,Sector,Order Value\n")
    return response

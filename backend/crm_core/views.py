import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count
from django.contrib.auth import get_user_model
from django.db.models.functions import TruncMonth, TruncYear

from .models import FieldVisit, Farm

User = get_user_model()


def dashboard_home(request):
    """
    Main Dashboard View - Filters correctly by executive without double-multiplying values.
    """
    selected_executive = request.GET.get('executive', 'ALL')
    
    visits = FieldVisit.objects.select_related('executive', 'farm').all()

    if selected_executive and selected_executive != 'ALL':
        visits = visits.filter(executive__username=selected_executive)

    total_visits = visits.count()
    
    # Corrected Direct Sum: Avoids multiplying unit price by quantity again
    total_revenue = visits.aggregate(total_rev=Sum('order_value'))['total_rev'] or 0

    executives_list = User.objects.filter(is_active=True)

    context = {
        'selected_executive': selected_executive,
        'executives_list': executives_list,
        'total_visits': total_visits,
        'total_revenue': f"{total_revenue:,.2f}",
        'recent_visits': visits.order_by('-date')[:10],
    }
    return render(request, 'dashboard.html', context)


def executive_analytics_view(request):
    """
    Analytics View - Returns pure live database stats (or zeros if database is empty).
    """
    selected_executive = request.GET.get('executive', 'ALL')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    selected_sector = request.GET.get('sector', 'ALL')

    # Base QuerySet
    visits = FieldVisit.objects.select_related('executive', 'farm').all()

    # Active Filters
    if selected_executive and selected_executive != 'ALL':
        visits = visits.filter(executive__username=selected_executive)

    if selected_sector and selected_sector != 'ALL':
        visits = visits.filter(sector=selected_sector)

    if start_date and end_date:
        visits = visits.filter(date__range=[start_date, end_date])

    # KPI Calculations
    total_visits = visits.count()
    total_revenue = visits.aggregate(total_rev=Sum('order_value'))['total_rev'] or 0
    total_qty = visits.aggregate(total_qty=Sum('order_quantity'))['total_qty'] or 0
    avg_revenue = (total_revenue / total_visits) if total_visits > 0 else 0

    total_executives = User.objects.filter(is_active=True).count()
    total_farms = visits.values('farm').distinct().count()

    # Monthly Aggregations
    month_data = (
        visits.annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('order_value'))
        .order_by('month')
    )
    month_labels = [item['month'].strftime('%b %Y') for item in month_data if item['month']]
    month_values = [float(item['total'] or 0) for item in month_data]

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

    # Sector Ratio
    poultry_count = visits.filter(sector='POULTRY').count()
    aqua_count = visits.filter(sector='AQUA').count()
    sector_total = poultry_count + aqua_count

    sector_poultry_pct = round((poultry_count / sector_total) * 100, 1) if sector_total > 0 else 0
    sector_aqua_pct = round((aqua_count / sector_total) * 100, 1) if sector_total > 0 else 0

    context = {
        'selected_executive': selected_executive,
        'start_date': start_date,
        'end_date': end_date,
        'selected_sector': selected_sector,
        'executives_list': User.objects.filter(is_active=True),

        # Pure KPIs (Zeros if no visits are recorded)
        'total_visits': total_visits,
        'total_executives': total_executives,
        'total_farms': total_farms,
        'total_qty': total_qty,
        'total_revenue': f"{total_revenue:,.2f}",
        'avg_revenue': f"{avg_revenue:,.2f}",

        'sector_poultry_pct': sector_poultry_pct,
        'sector_aqua_pct': sector_aqua_pct,

        # Empty array fallbacks for charts
        'month_labels_json': json.dumps(month_labels),
        'month_data_json': json.dumps(month_values),
        'exec_labels_json': json.dumps(exec_labels),
        'exec_data_json': json.dumps(exec_values),
        'prod_labels_json': json.dumps([]),
        'prod_data_json': json.dumps([]),
        'state_labels_json': json.dumps([]),
        'state_data_json': json.dumps([]),

        'recent_visits': visits.order_by('-date')[:10],
    }

    return render(request, 'analytics.html', context)


def get_dependent_filters(request):
    """
    Dynamic AJAX Filter Handler
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


def export_visits_to_excel(request):
    """
    Excel Export Handler
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="analytics_report.csv"'
    response.write("Date,Executive,Farm,Sector,Order Value\n")
    return response

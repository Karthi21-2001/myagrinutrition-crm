import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.db.models.functions import TruncMonth, TruncYear

from .models import FieldVisit, Farm

User = get_user_model()

def executive_analytics_view(request):
    """
    Analytics View - Starts with 0 data unless real visits are recorded.
    """
    # 1. Capture Filters
    selected_executive = request.GET.get('executive', 'ALL')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    selected_sector = request.GET.get('sector', 'ALL')

    # 2. Base QuerySet
    visits = FieldVisit.objects.select_related('executive', 'farm').all()

    # 3. Apply Active Filters
    if selected_executive and selected_executive != 'ALL':
        visits = visits.filter(executive_id=selected_executive)

    if selected_sector and selected_sector != 'ALL':
        visits = visits.filter(sector=selected_sector)

    if start_date and end_date:
        visits = visits.filter(date__range=[start_date, end_date])

    # 4. Aggregations & KPIs (Zero Defaults)
    total_visits = visits.count()
    
    revenue_agg = visits.aggregate(total_rev=Sum('order_value'))
    total_revenue = revenue_agg['total_rev'] or 0

    qty_agg = visits.aggregate(total_qty=Sum('order_quantity'))
    total_qty = qty_agg['total_qty'] or 0

    avg_revenue = (total_revenue / total_visits) if total_visits > 0 else 0

    total_executives = User.objects.filter(is_active=True).count()
    total_farms = visits.values('farm').distinct().count()

    # 5. Month-wise Trend Data
    month_data = (
        visits.annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('order_value'))
        .order_by('month')
    )
    month_labels = [item['month'].strftime('%b %Y') for item in month_data if item['month']]
    month_values = [float(item['total'] or 0) for item in month_data]

    # 6. Year-wise Trend Data
    year_data = (
        visits.annotate(year=TruncYear('date'))
        .values('year')
        .annotate(total=Sum('order_value'))
        .order_by('year')
    )
    year_labels = [item['year'].strftime('%Y') for item in year_data if item['year']]
    year_values = [float(item['total'] or 0) for item in year_data]

    # 7. Executive Breakdown
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

    # 8. Business Sector Calculations
    poultry_count = visits.filter(sector='POULTRY').count()
    aqua_count = visits.filter(sector='AQUA').count()
    sector_total = poultry_count + aqua_count
    
    sector_poultry_pct = round((poultry_count / sector_total) * 100, 1) if sector_total > 0 else 0
    sector_aqua_pct = round((aqua_count / sector_total) * 100, 1) if sector_total > 0 else 0

    # 9. Top Farms List
    top_farms_qs = (
        visits.values('farm__name')
        .annotate(revenue=Sum('order_value'))
        .order_by('-revenue')[:5]
    )
    top_farms = [
        {'name': farm['farm__name'], 'revenue': farm['revenue']}
        for farm in top_farms_qs
    ]

    # 10. Table List
    recent_visits = visits.order_by('-date')[:10]
    executives_list = User.objects.all()

    # Context Payload
    context = {
        'selected_executive': selected_executive,
        'start_date': start_date,
        'end_date': end_date,
        'selected_sector': selected_sector,
        'executives_list': executives_list,

        # Metrics (Start cleanly at 0)
        'total_visits': total_visits,
        'total_executives': total_executives,
        'total_farms': total_farms,
        'total_qty': total_qty,
        'total_revenue': f"{total_revenue:,.2f}",
        'avg_revenue': f"{avg_revenue:,.2f}",

        # Growth Percentage Badges
        'visits_growth': '0%',
        'farms_expansion': '0%',
        'qty_velocity': '0%',
        'revenue_growth': '0%',
        'avg_growth': '0%',

        # Sectors
        'sector_poultry_pct': sector_poultry_pct,
        'sector_aqua_pct': sector_aqua_pct,

        # Dynamic JSON arrays for Charts (Empty [] if no logs exist)
        'month_labels_json': json.dumps(month_labels),
        'month_data_json': json.dumps(month_values),
        'year_labels_json': json.dumps(year_labels),
        'year_data_json': json.dumps(year_values),
        'exec_labels_json': json.dumps(exec_labels),
        'exec_data_json': json.dumps(exec_values),
        'prod_labels_json': json.dumps([]),
        'prod_data_json': json.dumps([]),
        'state_labels_json': json.dumps([]),
        'state_data_json': json.dumps([]),
        'problem_labels_json': json.dumps([]),
        'problem_data_json': json.dumps([]),

        # Empty Tables
        'top_farms': top_farms,
        'recent_visits': recent_visits,
    }

    return render(request, 'analytics.html', context)


def get_dependent_filters(request):
    """
    API endpoint for dynamic AJAX dropdown filters
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
    Export Engine
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="analytics_matrix.csv"'
    response.write("Date,Executive,Farm,Sector,Order Value\n")
    return response

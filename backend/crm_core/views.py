import json
from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth, TruncYear
from django.http import HttpResponse

# Import your models here (adjust app path as needed)
# from .models import Visit, Farm, Product, Problem

User = get_user_model()


def analytics_dashboard(request):
    # -------------------------------------------------------------------------
    # 1. EXTRACT QUERY PARAMETERS & FILTERS
    # -------------------------------------------------------------------------
    selected_executive = request.GET.get('executive', 'ALL')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    selected_sector = request.GET.get('sector', 'ALL')

    # Base queryset for Visits
    visits_qs = Visit.objects.all()

    # Filter: Executive
    if selected_executive and selected_executive != 'ALL':
        visits_qs = visits_qs.filter(executive_id=selected_executive)

    # Filter: Date Range
    if start_date:
        visits_qs = visits_qs.filter(date__gte=start_date)
    if end_date:
        visits_qs = visits_qs.filter(date__lte=end_date)

    # Filter: Sector (Poultry vs Aqua)
    if selected_sector and selected_sector != 'ALL':
        visits_qs = visits_qs.filter(sector__iexact=selected_sector)

    # -------------------------------------------------------------------------
    # 2. KPI CALCULATIONS
    # -------------------------------------------------------------------------
    total_visits = visits_qs.count()
    total_executives = visits_qs.values('executive').distinct().count()
    total_farms = visits_qs.values('farm').distinct().count()

    # Total order quantity & Revenue
    aggregates = visits_qs.aggregate(
        total_qty=Sum('order_quantity'),
        total_revenue=Sum('order_value'),
        avg_revenue=Avg('order_value')
    )

    total_qty = aggregates['total_qty'] or 0
    total_revenue = aggregates['total_revenue'] or 0
    avg_revenue = aggregates['avg_revenue'] or 0

    # -------------------------------------------------------------------------
    # 3. CHART 1 & 2: MONTH-WISE & YEAR-WISE REVENUE TRENDS
    # -------------------------------------------------------------------------
    # Monthly aggregate
    monthly_data = (
        visits_qs.annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(revenue=Sum('order_value'))
        .order_by('month')
    )
    month_labels = [item['month'].strftime('%b %Y') for item in monthly_data if item['month']]
    month_values = [float(item['revenue'] or 0) for item in monthly_data]

    # Yearly aggregate
    yearly_data = (
        visits_qs.annotate(year=TruncYear('date'))
        .values('year')
        .annotate(revenue=Sum('order_value'))
        .order_by('year')
    )
    year_labels = [item['year'].strftime('%Y') for item in yearly_data if item['year']]
    year_values = [float(item['revenue'] or 0) for item in yearly_data]

    # -------------------------------------------------------------------------
    # 4. CHART 3: REVENUE BY EXECUTIVE
    # -------------------------------------------------------------------------
    exec_data = (
        visits_qs.values('executive__first_name', 'executive__username')
        .annotate(revenue=Sum('order_value'))
        .order_by('-revenue')[:10]
    )
    exec_labels = [
        item['executive__first_name'] or item['executive__username']
        for item in exec_data
    ]
    exec_values = [float(item['revenue'] or 0) for item in exec_data]

    # -------------------------------------------------------------------------
    # 5. CHART 4: PRODUCT ALLOCATION (DONUT)
    # -------------------------------------------------------------------------
    # Assuming M2M or FK to Product on Visit
    prod_data = (
        visits_qs.values('product__name')
        .annotate(volume=Sum('order_quantity'))
        .order_by('-volume')[:5]
    )
    prod_labels = [item['product__name'] or 'Uncategorized' for item in prod_data]
    prod_values = [item['volume'] or 0 for item in prod_data]

    # -------------------------------------------------------------------------
    # 6. CHART 5: VISITS BY STATE
    # -------------------------------------------------------------------------
    state_data = (
        visits_qs.values('state')
        .annotate(visit_count=Count('id'))
        .order_by('-visit_count')[:5]
    )
    state_labels = [item['state'] or 'Unknown' for item in state_data]
    state_values = [item['visit_count'] for item in state_data]

    # -------------------------------------------------------------------------
    # 7. CHART 6: OBSERVED FIELD PROBLEMS (DONUT)
    # -------------------------------------------------------------------------
    problem_data = (
        visits_qs.values('problem_observed__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    problem_labels = [item['problem_observed__name'] or 'General Check' for item in problem_data]
    problem_values = [item['count'] for item in problem_data]

    # -------------------------------------------------------------------------
    # 8. TOP FARMS BY REVENUE (LEDGER TABLE)
    # -------------------------------------------------------------------------
    top_farms = (
        visits_qs.values('farm__name')
        .annotate(revenue=Sum('order_value'))
        .order_by('-revenue')[:6]
    )
    top_farms_list = [
        {'name': farm['farm__name'], 'revenue': f"{farm['revenue'] or 0:,.2f}"}
        for farm in top_farms
    ]

    # -------------------------------------------------------------------------
    # 9. PIPELINE TEMPERATURE & SECTOR RATIOS
    # -------------------------------------------------------------------------
    # Pipeline percentages calculation
    total_pipeline_items = visits_qs.exclude(pipeline_status__isnull=True).count() or 1
    hot_count = visits_qs.filter(pipeline_status__iexact='HOT').count()
    warm_count = visits_qs.filter(pipeline_status__iexact='WARM').count()
    cold_count = visits_qs.filter(pipeline_status__iexact='COLD').count()

    pipeline_hot = round((hot_count / total_pipeline_items) * 100)
    pipeline_warm = round((warm_count / total_pipeline_items) * 100)
    pipeline_cold = round((cold_count / total_pipeline_items) * 100)

    # Sector distribution percentages
    sector_total = visits_qs.count() or 1
    poultry_count = visits_qs.filter(sector__iexact='POULTRY').count()
    aqua_count = visits_qs.filter(sector__iexact='AQUA').count()

    sector_poultry_pct = round((poultry_count / sector_total) * 100)
    sector_aqua_pct = round((aqua_count / sector_total) * 100)

    # -------------------------------------------------------------------------
    # 10. RECENT VISIT SUMMARY LOG (TABLE) & EXECUTIVES DROPDOWN
    # -------------------------------------------------------------------------
    recent_visits = visits_qs.select_related('executive', 'farm').order_by('-date')[:10]
    executives_list = User.objects.filter(is_active=True).order_by('first_name')

    # -------------------------------------------------------------------------
    # CONTEXT COMPOSITION
    # -------------------------------------------------------------------------
    context = {
        # Active Filter States
        'selected_executive': selected_executive,
        'start_date': start_date,
        'end_date': end_date,
        'selected_sector': selected_sector,
        'executives_list': executives_list,

        # Top KPIs
        'total_visits': f"{total_visits:,}",
        'total_executives': total_executives,
        'total_farms': total_farms,
        'total_qty': f"{total_qty:,}",
        'total_revenue': f"{total_revenue:,.2f}",
        'avg_revenue': f"{avg_revenue:,.2f}",
        'visits_growth': '12%',
        'farms_expansion': '8%',
        'qty_velocity': '15%',
        'revenue_growth': '18%',
        'avg_growth': '5%',

        # Tables / Collections
        'top_farms': top_farms_list,
        'recent_visits': recent_visits,

        # Pipeline & Sector Percentages
        'pipeline_hot': pipeline_hot,
        'pipeline_warm': pipeline_warm,
        'pipeline_cold': pipeline_cold,
        'sector_poultry_pct': sector_poultry_pct,
        'sector_aqua_pct': sector_aqua_pct,

        # Chart JSON Encodings (safe for template insertion)
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
        'problem_labels_json': json.dumps(problem_labels),
        'problem_data_json': json.dumps(problem_values),
    }

    return render(request, 'analytics_dashboard.html', context)

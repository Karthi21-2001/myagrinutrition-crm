import json
import openpyxl
import requests
from decimal import Decimal

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth, TruncYear
from django.views.decorators.http import require_GET, require_POST

from .models import VisitLog, PipelineItem, OrderItem

User = get_user_model()


# ==============================================================================
# 1. FORM DISPLAY & SUBMISSION
# ==============================================================================

@login_required
def render_form(request):
    """Renders the HTML form template for field visits."""
    return render(request, 'farm_visit_form.html')


@login_required
@require_POST
@transaction.atomic
def save_visit_log(request):
    """Saves field visit data along with dynamic pipeline and order items."""
    POST = request.POST

    visit = VisitLog(
        executive=request.user,
        farm_name=POST.get('farm_name', '').strip(),
        owner_name=POST.get('owner_name', '').strip(),
        contact_number=POST.get('contact_number', '').strip(),
        latitude=POST.get('latitude') or None,
        longitude=POST.get('longitude') or None,
        district=POST.get('district', '').strip(),
        area=POST.get('area', '').strip(),
        state=POST.get('state', '').strip(),
        business_type=POST.get('business_type', 'Poultry'),
        sub_business_type=POST.get('sub_business_type', '').strip(),
        farm_problem=POST.get('farm_problem', '').strip(),
    )

    if visit.business_type == 'Poultry':
        visit.chicks_count = int(POST.get('chicks_count') or 0)
        visit.grower_count = int(POST.get('grower_count') or 0)
        visit.layer_count = int(POST.get('layer_count') or 0)
        visit.culling_bird_count = int(POST.get('culling_bird_count') or 0)
    elif visit.business_type == 'Aqua':
        visit.pond_acre = float(POST.get('pond_acre') or 0.00)
        visit.pond_doc = int(POST.get('pond_doc') or 0)
        visit.fish_variety = POST.get('fish_variety', '').strip()

    visit.save()

    # Save Dynamic Pipeline Rows
    pipeline_products = POST.getlist('pipeline_discussed_product[]')
    potential_quantities = POST.getlist('pipeline_potential_quantity[]')
    target_quantities = POST.getlist('pipeline_target_quantity[]')
    pipeline_units = POST.getlist('pipeline_unit_type[]')
    statuses = POST.getlist('pipeline_process_status[]')
    conversions = POST.getlist('pipeline_conversion_percentage[]')

    for i in range(len(pipeline_products)):
        prod_name = pipeline_products[i].strip()
        if prod_name:
            PipelineItem.objects.create(
                visit=visit,
                product_name=prod_name,
                potential_quantity=int(potential_quantities[i] or 0),
                target_quantity=int(target_quantities[i] or 0),
                unit_type=pipeline_units[i] if i < len(pipeline_units) else 'KG',
                process_status=statuses[i] if i < len(statuses) else 'Warm',
                conversion_percentage=int(conversions[i] or 0),
            )

    # Save Dynamic Order Rows
    order_products = POST.getlist('discussed_product[]')
    sale_quantities = POST.getlist('sale_quantity[]')
    order_units = POST.getlist('unit_type[]')
    prices = POST.getlist('primary_price[]')

    for i in range(len(order_products)):
        prod_name = order_products[i].strip()
        if prod_name:
            OrderItem.objects.create(
                visit=visit,
                product_name=prod_name,
                sale_quantity=int(sale_quantities[i] or 0),
                unit_type=order_units[i] if i < len(order_units) else 'KG',
                primary_price=float(prices[i] or 0.00),
            )

    return redirect('analytics_dashboard')


# ==============================================================================
# 2. ANALYTICS DASHBOARD VIEW
# ==============================================================================

@login_required
def analytics_dashboard(request):
    """Computes KPIs, aggregation metrics, and chart payloads for the main dashboard."""
    selected_executive = request.GET.get('executive', 'ALL')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    selected_sector = request.GET.get('sector', 'ALL')

    # Queryset filter chain
    visits_qs = VisitLog.objects.all()

    if selected_executive and selected_executive != 'ALL':
        visits_qs = visits_qs.filter(executive_id=selected_executive)
    if start_date:
        visits_qs = visits_qs.filter(created_at__date__gte=start_date)
    if end_date:
        visits_qs = visits_qs.filter(created_at__date__lte=end_date)
    if selected_sector and selected_sector != 'ALL':
        visits_qs = visits_qs.filter(business_type__iexact=selected_sector)

    # Metrics
    total_visits = visits_qs.count()
    total_executives = visits_qs.values('executive').distinct().count()
    total_farms = visits_qs.values('farm_name').distinct().count()

    order_aggregates = OrderItem.objects.filter(visit__in=visits_qs).aggregate(
        total_qty=Sum('sale_quantity'),
        total_revenue=Sum(models.F('sale_quantity') * models.F('primary_price'), output_field=models.DecimalField())
    )

    total_qty = order_aggregates['total_qty'] or 0
    total_revenue = order_aggregates['total_revenue'] or 0
    avg_revenue = (total_revenue / total_visits) if total_visits > 0 else 0

    # Chart 1: Monthly Trends
    monthly_data = (
        visits_qs.annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(revenue=Sum(models.F('orders__sale_quantity') * models.F('orders__primary_price')))
        .order_by('month')
    )
    month_labels = [item['month'].strftime('%b %Y') for item in monthly_data if item['month']]
    month_values = [float(item['revenue'] or 0) for item in monthly_data]

    # Chart 2: Top Products Allocation
    prod_data = (
        OrderItem.objects.filter(visit__in=visits_qs)
        .values('product_name')
        .annotate(volume=Sum('sale_quantity'))
        .order_by('-volume')[:5]
    )
    prod_labels = [item['product_name'] or 'Uncategorized' for item in prod_data]
    prod_values = [item['volume'] or 0 for item in prod_data]

    # Pipeline Metrics
    pipeline_qs = PipelineItem.objects.filter(visit__in=visits_qs)
    total_pipeline = pipeline_qs.count() or 1
    hot_count = pipeline_qs.filter(process_status__iexact='Hot').count()
    warm_count = pipeline_qs.filter(process_status__iexact='Warm').count()
    cold_count = pipeline_qs.filter(process_status__iexact='Cold').count()

    context = {
        'selected_executive': selected_executive,
        'start_date': start_date,
        'end_date': end_date,
        'selected_sector': selected_sector,
        'executives_list': User.objects.filter(is_active=True).order_by('first_name'),

        'total_visits': f"{total_visits:,}",
        'total_executives': total_executives,
        'total_farms': total_farms,
        'total_qty': f"{total_qty:,}",
        'total_revenue': f"{total_revenue:,.2f}",
        'avg_revenue': f"{avg_revenue:,.2f}",

        'pipeline_hot': round((hot_count / total_pipeline) * 100),
        'pipeline_warm': round((warm_count / total_pipeline) * 100),
        'pipeline_cold': round((cold_count / total_pipeline) * 100),

        'month_labels_json': json.dumps(month_labels),
        'month_data_json': json.dumps(month_values),
        'prod_labels_json': json.dumps(prod_labels),
        'prod_data_json': json.dumps(prod_values),
    }

    return render(request, 'analytics.html', context)


# ==============================================================================
# 3. ANALYTICS REPORT VIEW (DETAILED PRINT/PDF VIEW)
# ==============================================================================

@login_required
def analytics_report(request):
    """Renders printable analytical reports and tabular summaries."""
    visits = VisitLog.objects.all().select_related('executive').prefetch_related('orders', 'pipeline_items')
    
    context = {
        'visits': visits,
        'total_count': visits.count()
    }
    return render(request, 'analytics_report.html', context)


# ==============================================================================
# 4. GEOLOCATION & EXPORT ENDPOINTS
# ==============================================================================

@require_GET
def get_location_details(request):
    """Reverse geocodes coordinates into State, District, and Area via OSM."""
    lat, lon = request.GET.get('lat'), request.GET.get('lon')
    if not lat or not lon:
        return JsonResponse({'error': 'Coordinates required'}, status=400)

    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        response = requests.get(url, headers={'User-Agent': 'AgriNutritionCRM/1.0'}, timeout=5)
        if response.status_code == 200:
            data = response.json().get('address', {})
            return JsonResponse({
                'area': data.get('suburb') or data.get('village') or data.get('town') or '',
                'district': data.get('state_district') or data.get('county') or '',
                'state': data.get('state', '')
            })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Geocoding service unavailable'}, status=502)


@login_required
def export_excel(request):
    """Generates an `.xlsx` file containing all field visits and revenue."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Visit Reports"

    ws.append(['ID', 'Executive', 'Date', 'Farm Name', 'Owner', 'Contact', 'Sector', 'Total Revenue'])

    for log in VisitLog.objects.all().select_related('executive'):
        ws.append([
            log.id,
            log.executive.get_full_name() or log.executive.username,
            log.created_at.strftime('%Y-%m-%d %H:%M'),
            log.farm_name,
            log.owner_name,
            log.contact_number,
            log.business_type,
            log.total_order_value
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Agrinutrition_Visit_Logs.xlsx"'
    wb.save(response)
    return response

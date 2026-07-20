import json
import logging
import traceback
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Q
from django.contrib.auth import get_user_model
from django.db.models.functions import TruncMonth

from .models import Farm, FarmVisitReport, VisitedProductDetail

User = get_user_model()
logger = logging.getLogger(__name__)


def executive_analytics_view(request):
    """
    Bulletproof Analytics View - Catches exceptions and logs tracebacks to Render console.
    """
    try:
        # 1. Capture Filters
        selected_executive = request.GET.get('executive', 'ALL')
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        selected_sector = request.GET.get('sector', 'ALL')

        # 2. QuerySets
        visits = FarmVisitReport.objects.select_related('executive', 'farm').all()
        products = VisitedProductDetail.objects.select_related('visit', 'visit__farm', 'visit__executive').all()

        # 3. Apply Active Filters Safely
        if selected_executive and selected_executive != 'ALL':
            if selected_executive.isdigit():
                visits = visits.filter(executive_id=int(selected_executive))
                products = products.filter(visit__executive_id=int(selected_executive))
            else:
                visits = visits.filter(executive__username=selected_executive)
                products = products.filter(visit__executive__username=selected_executive)

        if selected_sector and selected_sector != 'ALL':
            visits = visits.filter(farm__business_type__iexact=selected_sector)
            products = products.filter(visit__farm__business_type__iexact=selected_sector)

        if start_date and end_date:
            visits = visits.filter(visit_date__range=[start_date, end_date])
            products = products.filter(visit__visit_date__range=[start_date, end_date])

        # 4. KPI Calculations
        total_visits = visits.count()

        revenue_agg = products.aggregate(total_rev=Sum('revenue_generated'))
        total_revenue = float(revenue_agg['total_rev'] or 0.0)

        qty_agg = products.aggregate(total_qty=Sum('sale_quantity'))
        total_qty = qty_agg['total_qty'] or 0

        avg_revenue = (total_revenue / total_visits) if total_visits > 0 else 0.0

        total_executives = User.objects.filter(is_active=True).count()
        total_farms = visits.values('farm').distinct().count()

        # 5. Sector Calculations
        poultry_count = visits.filter(farm__business_type__iexact='Poultry').count()
        aqua_count = visits.filter(farm__business_type__iexact='Aqua').count()
        sector_total = poultry_count + aqua_count

        sector_poultry_pct = round((poultry_count / sector_total) * 100, 1) if sector_total > 0 else 0
        sector_aqua_pct = round((aqua_count / sector_total) * 100, 1) if sector_total > 0 else 0

        # 6. Monthly Data
        month_labels, month_values = [], []
        if products.exists():
            month_data = (
                products.annotate(month=TruncMonth('visit__visit_date'))
                .values('month')
                .annotate(total=Sum('revenue_generated'))
                .order_by('month')
            )
            for item in month_data:
                if item.get('month'):
                    month_labels.append(item['month'].strftime('%b %Y'))
                    month_values.append(float(item['total'] or 0))

        # 7. Executive Breakdown
        exec_labels, exec_values = [], []
        if products.exists():
            exec_data = (
                products.values('visit__executive__first_name', 'visit__executive__username')
                .annotate(total=Sum('revenue_generated'))
                .order_by('-total')[:5]
            )
            for item in exec_data:
                name = item.get('visit__executive__first_name') or item.get('visit__executive__username') or 'Unassigned'
                exec_labels.append(name)
                exec_values.append(float(item['total'] or 0))

        # 8. Top Farms
        top_farms = []
        if products.exists():
            top_farms_qs = (
                products.values('visit__farm__farm_name')
                .annotate(revenue=Sum('revenue_generated'))
                .order_by('-revenue')[:5]
            )
            for item in top_farms_qs:
                top_farms.append({
                    'name': item.get('visit__farm__farm_name', 'Unknown Farm'),
                    'revenue': float(item.get('revenue') or 0)
                })

        context = {
            'selected_executive': selected_executive,
            'start_date': start_date,
            'end_date': end_date,
            'selected_sector': selected_sector,
            'executives_list': User.objects.filter(is_active=True),

            # Metrics
            'total_visits': total_visits,
            'total_executives': total_executives,
            'total_farms': total_farms,
            'total_qty': total_qty,
            'total_revenue': f"{total_revenue:,.2f}",
            'avg_revenue': f"{avg_revenue:,.2f}",

            'sector_poultry_pct': sector_poultry_pct,
            'sector_aqua_pct': sector_aqua_pct,

            # Charts
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
            'recent_visits': visits.order_by('-visit_date')[:10],
        }

        return render(request, 'analytics.html', context)

    except Exception as e:
        # Print full error stack trace to Render logs for easy debugging
        print("=== ERROR IN EXECUTIVE_ANALYTICS_VIEW ===")
        print(traceback.format_exc())
        logger.error(f"Error rendering analytics page: {str(e)}")
        
        # Render clean zero fallback context instead of breaking the page
        fallback_context = {
            'selected_executive': 'ALL',
            'executives_list': User.objects.filter(is_active=True),
            'total_visits': 0,
            'total_executives': 0,
            'total_farms': 0,
            'total_qty': 0,
            'total_revenue': "0.00",
            'avg_revenue': "0.00",
            'sector_poultry_pct': 0,
            'sector_aqua_pct': 0,
            'month_labels_json': json.dumps([]),
            'month_data_json': json.dumps([]),
            'exec_labels_json': json.dumps([]),
            'exec_data_json': json.dumps([]),
            'prod_labels_json': json.dumps([]),
            'prod_data_json': json.dumps([]),
            'state_labels_json': json.dumps([]),
            'state_data_json': json.dumps([]),
            'top_farms': [],
            'recent_visits': [],
        }
        return render(request, 'analytics.html', fallback_context)


def dashboard_home(request):
    return executive_analytics_view(request)


def dashboard_analytics(request):
    return executive_analytics_view(request)


def get_dependent_filters(request):
    executive_id = request.GET.get('executive_id')
    sector = request.GET.get('sector')

    farms_qs = Farm.objects.all()

    if executive_id and executive_id != 'ALL' and executive_id.isdigit():
        farms_qs = farms_qs.filter(executive_id=int(executive_id))

    if sector and sector != 'ALL':
        farms_qs = farms_qs.filter(business_type__iexact=sector)

    farms_data = list(farms_qs.values('id', 'farm_name'))
    return JsonResponse({'status': 'success', 'farms': farms_data}, safe=False)


def get_location_details(request):
    return JsonResponse({'status': 'success', 'location': ''})


def export_visits_to_excel(request):
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

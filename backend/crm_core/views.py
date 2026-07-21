import json
import logging
import openpyxl

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import (
    Avg, Count, F, Q, Sum, Case, When, IntegerField, FloatField, DecimalField, Value, ExpressionWrapper
)
from django.db.models.functions import TruncMonth, TruncYear, Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from django.shortcuts import render, redirect, get_object_or_400
from django.contrib import messages
from django.db.models import Sum, Count, F, Avg
from django.db.models.functions import TruncMonth, TruncYear
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

# Import your models (adjust model names if yours differ)
from .models import VisitLog, PipelineItem, OrderItem, Executive, Farm

# Local Application Imports
from .forms import ExecutiveSignUpForm
from .models import Farm, FarmVisitReport, VisitedProductDetail

logger = logging.getLogger(__name__)
User = get_user_model()


# Helper function to render templates safely across folder structures
def render_safe(request, template_names, context=None):
    if isinstance(template_names, str):
        template_names = [template_names]
    
    for t in template_names:
        try:
            return render(request, t, context)
        except TemplateDoesNotExist:
            continue
    raise TemplateDoesNotExist(f"None of these templates exist: {template_names}")


# ==========================================
# 🔐 EXECUTIVE AUTHENTICATION CONTROLLERS
# ==========================================

def register_user(request):
    if request.method == 'POST':
        form = ExecutiveSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            if user.is_staff or user.is_superuser:
                return redirect('dashboard_home')
            return redirect('render_visit_form')
    else:
        form = ExecutiveSignUpForm()
    return render_safe(request, ['crm_core/register.html', 'register.html'], {'form': form})


def login_user(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                if user.is_staff or user.is_superuser:
                    return redirect('dashboard_home')
                return redirect('render_visit_form')
    else:
        form = AuthenticationForm()
    return render_safe(request, ['crm_core/login.html', 'login.html'], {'form': form})


def logout_user(request):
    logout(request)
    return redirect('login_user')


# ==========================================
# 🌱 AGRI-CORE MANAGEMENT FUNCTIONALITY
# ==========================================

@login_required(login_url='/crm/login/')
def render_visit_form(request):
    return render_safe(request, ['crm_core/farm_visit_form.html', 'farm_visit_form.html'])


@login_required(login_url='/crm/login/')
def save_farm_visit(request):
    if request.method == 'POST':
        farm_name = request.POST.get('farm_name')
        owner_name = request.POST.get('owner_name')
        contact_number = request.POST.get('contact_number')
        business_type = request.POST.get('business_type', 'Poultry')
        sub_segment = request.POST.get('sub_business_type_select', '').strip()
        district = request.POST.get('district', '').strip()
        area = request.POST.get('area', '').strip()
        state = request.POST.get('state', '').strip()
        farm_problem = request.POST.get('farm_problem')

        if not state or state.lower() in ['state', 'unknown state', '']:
            state = 'Tamil Nadu'

        lat = request.POST.get('latitude')
        lon = request.POST.get('longitude')
        latitude = float(lat) if lat else None
        longitude = float(lon) if lon else None

        current_user = request.user if request.user.is_authenticated else None

        try:
            with transaction.atomic():
                farm_instance, created = Farm.objects.get_or_create(
                    farm_name=farm_name,
                    owner_name=owner_name,
                    contact_number=contact_number,
                    defaults={
                        'executive': current_user,
                        'business_type': business_type,
                        'sub_segment': sub_segment,
                        'state': state,
                        'district': district,
                        'area': area,
                        'latitude': latitude,
                        'longitude': longitude,
                    }
                )

                if not created:
                    if business_type:
                        farm_instance.business_type = business_type
                    if sub_segment:
                        farm_instance.sub_segment = sub_segment
                    farm_instance.state = state
                    farm_instance.district = district
                    farm_instance.area = area
                    farm_instance.save()

                visit_record = FarmVisitReport.objects.create(
                    farm=farm_instance,
                    executive=current_user,
                    farm_problem=farm_problem
                )

                # Process Sales Order Products
                order_products = request.POST.getlist('discussed_product[]')
                sale_quantities = request.POST.getlist('sale_quantity[]')
                unit_types = request.POST.getlist('unit_type[]')
                primary_prices = request.POST.getlist('primary_price[]')

                for i in range(len(order_products)):
                    prod_name = order_products[i].strip()
                    if not prod_name:
                        continue

                    s_qty = int(sale_quantities[i]) if (i < len(sale_quantities) and sale_quantities[i]) else 0
                    unit = unit_types[i] if i < len(unit_types) else 'KG'
                    price = float(primary_prices[i]) if (i < len(primary_prices) and primary_prices[i]) else 0.00

                    VisitedProductDetail.objects.create(
                        visit=visit_record,
                        product_name=prod_name,
                        potential_quantity=0,
                        target_quantity=0,
                        sale_quantity=s_qty,
                        unit_type=unit,
                        primary_price=price,
                        revenue_generated=price * s_qty,
                        process_status='Hot' if s_qty > 0 else 'Warm',
                        conversion_percentage=100 if s_qty > 0 else 0
                    )

                # Process Pipeline Products
                pipeline_products = request.POST.getlist('pipeline_discussed_product[]')
                p_quantities = request.POST.getlist('pipeline_potential_quantity[]')
                t_quantities = request.POST.getlist('pipeline_target_quantity[]')
                p_unit_types = request.POST.getlist('pipeline_unit_type[]')
                p_statuses = request.POST.getlist('pipeline_process_status[]')
                p_conv_percentages = request.POST.getlist('pipeline_conversion_percentage[]')

                for i in range(len(pipeline_products)):
                    pipe_prod_name = pipeline_products[i].strip()
                    if not pipe_prod_name:
                        continue

                    p_qty = int(p_quantities[i]) if (i < len(p_quantities) and p_quantities[i]) else 0
                    t_qty = int(t_quantities[i]) if (i < len(t_quantities) and t_quantities[i]) else 0
                    p_unit = p_unit_types[i] if i < len(p_unit_types) else 'KG'
                    status = p_statuses[i] if i < len(p_statuses) else 'Warm'
                    conv_pct = int(p_conv_percentages[i]) if (i < len(p_conv_percentages) and p_conv_percentages[i]) else 0

                    VisitedProductDetail.objects.create(
                        visit=visit_record,
                        product_name=pipe_prod_name,
                        potential_quantity=p_qty,
                        target_quantity=t_qty,
                        sale_quantity=0,
                        primary_price=0.00,
                        revenue_generated=0.00,
                        unit_type=p_unit,
                        process_status=status,
                        conversion_percentage=conv_pct
                    )

            messages.success(request, "Agri-Field visit logging record processed successfully!")
            if request.user.is_staff or request.user.is_superuser:
                return redirect('dashboard_home')

            return render_safe(request, ['crm_core/farm_visit_form.html', 'farm_visit_form.html'], {'saved_data': request.POST})

        except Exception as e:
            logger.error(f"Error in save_farm_visit: {str(e)}", exc_info=True)
            messages.error(request, f"Database transaction block failed: {str(e)}")
            return render_safe(request, ['crm_core/farm_visit_form.html', 'farm_visit_form.html'], {'saved_data': request.POST})

    return redirect('render_visit_form')


# ==========================================
# 📥 EXCEL EXPORT ENGINE
# ==========================================

@csrf_exempt
def export_visits_to_excel(request):
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()
    executive_filter = request.GET.get('executive', '').strip()
    state_filter = request.GET.get('state', '').strip()
    district_filter = request.GET.get('district', '').strip()
    business_type = request.GET.get('business_type', '').strip()
    sub_segment_filter = request.GET.get('sub_segment', '').strip()

    export_filters = Q()

    if business_type and business_type not in ['All', 'All Sectors']:
        export_filters &= Q(farm__business_type__iexact=business_type)
    if sub_segment_filter and sub_segment_filter != 'All':
        export_filters &= Q(farm__sub_segment__iexact=sub_segment_filter)
    if state_filter and state_filter not in ['All', 'All States']:
        export_filters &= Q(farm__state__iexact=state_filter)
    if district_filter and district_filter not in ['All', 'All Districts']:
        export_filters &= Q(farm__district__iexact=district_filter)
    if executive_filter and executive_filter not in ['All', 'All Executives']:
        export_filters &= Q(executive__username__iexact=executive_filter)

    if start_date_str:
        try:
            export_filters &= Q(visit_date__date__gte=start_date_str)
        except ValueError:
            pass
    if end_date_str:
        try:
            export_filters &= Q(visit_date__date__lte=end_date_str)
        except ValueError:
            pass

    wb = openpyxl.Workbook()
    ws_data = wb.active
    ws_data.title = "Field Visit Database Log"
    ws_data.views.sheetView[0].showGridLines = True

    dark_slate, border_color = "0F172A", "CBD5E1"
    thin_border = Border(
        left=Side(style='thin', color=border_color), right=Side(style='thin', color=border_color),
        top=Side(style='thin', color=border_color), bottom=Side(style='thin', color=border_color)
    )

    headers = [
        'Visit Date', 'Executive Name', 'Farm Name', 'Owner Name', 'Contact Number', 
        'Sector Segment', 'Sub-Segment', 'State', 'District', 'Area / Suburb', 
        'Farm Problem Observed', 'Chicks Count', 'Grower Count', 'Layer Count', 'Culling Bird',
        'Product Name', 'Sale Qty', 'Price (INR)', 'Revenue Generated',
        'Poten. Qty', 'Target Qty', 'Units', 'Process Stage', 'conv (%)', 'Live GPS Link'
    ]

    for col_idx, text in enumerate(headers, 1):
        cell = ws_data.cell(row=1, column=col_idx, value=text)
        cell.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color=dark_slate, end_color=dark_slate, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws_data.row_dimensions[1].height = 28

    all_visits = FarmVisitReport.objects.filter(export_filters).select_related(
        'farm', 'executive'
    ).prefetch_related('visited_products').order_by('-visit_date')

    current_row = 2
    for v in all_visits:
        f = v.farm
        products = list(v.visited_products.all())
        product_loop_list = products if products else [None]

        for p in product_loop_list:
            ws_data.cell(row=current_row, column=1, value=v.visit_date.strftime("%Y-%m-%d %H:%M") if v.visit_date else "")
            ws_data.cell(row=current_row, column=2, value=v.executive.username if v.executive else "")
            ws_data.cell(row=current_row, column=3, value=f.farm_name if f else "")
            ws_data.cell(row=current_row, column=4, value=f.owner_name if f else "")
            ws_data.cell(row=current_row, column=5, value=f.contact_number if f else "")
            ws_data.cell(row=current_row, column=6, value=f.business_type if f else "")
            ws_data.cell(row=current_row, column=7, value=f.sub_segment if (f and f.sub_segment) else "") 
            ws_data.cell(row=current_row, column=8, value=f.state if f else "")
            ws_data.cell(row=current_row, column=9, value=f.district if f else "")
            ws_data.cell(row=current_row, column=10, value=f.area if f else "")

            ws_data.cell(row=current_row, column=11, value=v.farm_problem if v.farm_problem else "None reported")
            
            ws_data.cell(row=current_row, column=12, value=getattr(f, 'chicks_count', 0) if f else 0)
            ws_data.cell(row=current_row, column=13, value=getattr(f, 'grower_count', 0) if f else 0)
            ws_data.cell(row=current_row, column=14, value=getattr(f, 'layer_count', 0) if f else 0)
            ws_data.cell(row=current_row, column=15, value=getattr(f, 'culling_bird_count', 0) if f else 0)

            ws_data.cell(row=current_row, column=16, value=p.product_name if p else "General Consult")
            ws_data.cell(row=current_row, column=17, value=p.sale_quantity if p else 0)
            ws_data.cell(row=current_row, column=18, value=float(p.primary_price) if p else 0.0)
            ws_data.cell(row=current_row, column=19, value=float(p.revenue_generated) if p else 0.0)

            ws_data.cell(row=current_row, column=20, value=p.potential_quantity if p else 0)
            ws_data.cell(row=current_row, column=21, value=p.target_quantity if p else 0)
            ws_data.cell(row=current_row, column=22, value=p.unit_type if p else "N/A")
            ws_data.cell(row=current_row, column=23, value=p.process_status if p else "N/A")
            ws_data.cell(row=current_row, column=24, value=f"{p.conversion_percentage}%" if p else "0%")

            gps_cell = ws_data.cell(row=current_row, column=25)
            if f and f.latitude and f.longitude:
                gps_cell.value = "View on Map"
                gps_cell.hyperlink = f"https://maps.google.com/?q={f.latitude},{f.longitude}"
                gps_cell.font = Font(name="Segoe UI", size=11, color="0000FF", underline="single")
            else:
                gps_cell.value = "No GPS Data"
                gps_cell.font = Font(name="Segoe UI", size=11, color="64748B", italic=True)

            for c_idx in range(1, 26):
                cell_item = ws_data.cell(row=current_row, column=c_idx)
                cell_item.border = thin_border
                if c_idx in [12, 13, 14, 15, 17, 20, 21, 24]: 
                    cell_item.alignment = Alignment(horizontal="center")

            current_row += 1

    if ws_data.max_row > 1:
        for col in ws_data.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_data.column_dimensions[col_letter].width = max(max_len + 4, 14)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="MyAgrinutrition_CRM_Field_Logs.xlsx"'
    wb.save(response)
    return response


# ==========================================
# 📊 DASHBOARDS & ADVANCED ANALYTICS PIPELINES
# ==========================================

def get_dashboard_context(request):
    total_rev = 0.0
    vol_sold = 0
    v_count = 0
    active_executives = 0
    total_farms_count = 0
    paid_orders_count = 0
    avg_order_value = 0.0
    conversion_rate = 0.0

    hot_pct, warm_pct, cold_pct = 0.0, 0.0, 0.0
    poultry_pct, aqua_pct = 0.0, 0.0

    combo_labels, combo_revenue, combo_volume = [], [], []
    top_prod_labels, top_prod_revenue = [], []
    pipeline_spread = {'actual': 0, 'target': 0, 'potential': 0}
    product_pricing_table = []
    exec_labels, exec_revenue, exec_conv_pct = [], [], []
    funnel_stages = []
    funnel_list = []
    geo_district_performance = []
    map_labels, map_revenue = [], []
    telemetry_audit_log = []
    bird_counts = [0, 0, 0, 0]
    bird_labels = ['Chicks', 'Growers', 'Layers', 'Culling Birds']
    reported_problems = []
    problems_list = []
    segment_breakdown = []
    visit_frequency_exec = []
    
    month_wise_qs = []
    month_wise_labels, month_wise_data = [], []
    year_wise_qs = []
    year_wise_labels, year_wise_data = [], []
    recent_visits_queryset = FarmVisitReport.objects.none()

    state_list = []
    district_list = []
    executive_list = []

    sel_state = request.GET.get('state', '').strip()
    sel_country = request.GET.get('country', '').strip()
    sel_district = request.GET.get('district', '').strip()
    sel_executive = request.GET.get('executive', '').strip()
    sel_month = request.GET.get('month', '').strip()
    sel_year = request.GET.get('year', '').strip()
    
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()

    try:
        farm_filters = Q()
        visit_filters = Q()
        product_filters = Q()

        if sel_state and sel_state not in ['All', 'All States', '']:
            farm_filters &= Q(state__iexact=sel_state)
            visit_filters &= Q(farm__state__iexact=sel_state)
            product_filters &= Q(visit__farm__state__iexact=sel_state)

        if sel_district and sel_district not in ['All', 'All Districts', '']:
            farm_filters &= Q(district__iexact=sel_district)
            visit_filters &= Q(farm__district__iexact=sel_district)
            product_filters &= Q(visit__farm__district__iexact=sel_district)

        if sel_executive and sel_executive not in ['All', 'All Executives', '']:
            farm_filters &= Q(executive__username__iexact=sel_executive)
            visit_filters &= Q(executive__username__iexact=sel_executive)
            product_filters &= Q(visit__executive__username__iexact=sel_executive)

        if sel_month and sel_month not in ['All', 'All Months', '']:
            try:
                m_val = int(sel_month)
                visit_filters &= Q(visit_date__month=m_val)
                product_filters &= Q(visit__visit_date__month=m_val)
            except ValueError:
                pass

        if sel_year and sel_year not in ['All', '']:
            try:
                y_val = int(sel_year)
                visit_filters &= Q(visit_date__year=y_val)
                product_filters &= Q(visit__visit_date__year=y_val)
            except ValueError:
                pass

        if start_date_str:
            try:
                visit_filters &= Q(visit_date__date__gte=start_date_str)
                product_filters &= Q(visit__visit_date__date__gte=start_date_str)
            except ValueError:
                pass

        if end_date_str:
            try:
                visit_filters &= Q(visit_date__date__lte=end_date_str)
                product_filters &= Q(visit__visit_date__date__lte=end_date_str)
            except ValueError:
                pass

        # 1. Primary Metrics Aggregations (COALESCE SAFE NULL HANDLING)
        v_count = FarmVisitReport.objects.filter(visit_filters).count()
        total_farms_count = Farm.objects.filter(farm_filters).count()
        active_executives = FarmVisitReport.objects.filter(visit_filters).values('executive').distinct().count()

        # Safely compute calculated revenue dynamically if revenue_generated is NULL
        computed_rev = ExpressionWrapper(
            Coalesce(F('sale_quantity'), 0) * Coalesce(F('primary_price'), 0.0, output_field=FloatField()),
            output_field=FloatField()
        )

        total_rev = VisitedProductDetail.objects.filter(product_filters).aggregate(
            total=Coalesce(Sum(Coalesce('revenue_generated', computed_rev)), 0.0, output_field=FloatField())
        )['total'] or 0.0

        vol_sold = VisitedProductDetail.objects.filter(product_filters).aggregate(
            total_qty=Coalesce(Sum('sale_quantity'), 0)
        )['total_qty'] or 0

        paid_orders_count = VisitedProductDetail.objects.filter(
            product_filters, 
            sale_quantity__gt=0
        ).count()

        avg_order_value = (total_rev / paid_orders_count) if paid_orders_count > 0 else 0.0

        total_leads = VisitedProductDetail.objects.filter(product_filters).count()
        if total_leads > 0:
            hot_count = VisitedProductDetail.objects.filter(product_filters, process_status__iexact='Hot').count()
            warm_count = VisitedProductDetail.objects.filter(product_filters, process_status__iexact='Warm').count()
            cold_count = VisitedProductDetail.objects.filter(product_filters, process_status__iexact='Cold').count()

            hot_pct = round((hot_count / total_leads) * 100, 1)
            warm_pct = round((warm_count / total_leads) * 100, 1)
            cold_pct = round((cold_count / total_leads) * 100, 1)
            conversion_rate = hot_pct

        if total_farms_count > 0:
            poultry_cnt = Farm.objects.filter(farm_filters, business_type__iexact='Poultry').count()
            aqua_cnt = Farm.objects.filter(farm_filters, business_type__iexact='Aqua').count()

            poultry_pct = round((poultry_cnt / total_farms_count) * 100, 1)
            aqua_pct = round((aqua_cnt / total_farms_count) * 100, 1)

        # 2. Time Series
        time_series_data = (
            VisitedProductDetail.objects.filter(product_filters)
            .annotate(month=TruncMonth('visit__visit_date'))
            .values('month')
            .annotate(
                revenue=Coalesce(Sum(Coalesce('revenue_generated', computed_rev)), 0.0, output_field=FloatField()),
                volume=Coalesce(Sum('sale_quantity'), 0)
            )
            .filter(month__isnull=False)
            .order_by('month')
        )

        combo_labels = [t['month'].strftime("%b %Y") for t in time_series_data if t.get('month')]
        combo_revenue = [float(t.get('revenue') or 0.0) for t in time_series_data]
        combo_volume = [int(t.get('volume') or 0) for t in time_series_data]

        # 3. Product Performance & Pricing Table
        product_performance = (
            VisitedProductDetail.objects.filter(product_filters)
            .values('product_name')
            .annotate(
                revenue=Coalesce(Sum(Coalesce('revenue_generated', computed_rev)), 0.0, output_field=FloatField()),
                qty_sold=Coalesce(Sum('sale_quantity'), 0)
            )
            .order_by('-revenue')
        )
        top_prod_labels = [p['product_name'] for p in product_performance if p.get('product_name')]
        top_prod_revenue = [float(p['revenue'] or 0.0) for p in product_performance]

        pipeline_spread_agg = VisitedProductDetail.objects.filter(product_filters).aggregate(
            actual=Coalesce(Sum('sale_quantity'), 0),
            target=Coalesce(Sum('target_quantity'), 0),
            potential=Coalesce(Sum('potential_quantity'), 0)
        )
        if pipeline_spread_agg:
            pipeline_spread = {k: (v or 0) for k, v in pipeline_spread_agg.items()}

        product_pricing_table = (
            VisitedProductDetail.objects.filter(product_filters)
            .values('product_name')
            .annotate(avg_unit_price=Coalesce(Avg('primary_price'), 0.0))
            .order_by('product_name')
        )

        # 4. Executive Performance
        executive_performance = (
            VisitedProductDetail.objects.filter(product_filters)
            .values('visit__executive__username')
            .annotate(
                revenue=Coalesce(Sum(Coalesce('revenue_generated', computed_rev)), 0.0, output_field=FloatField()),
                total_items=Count('id'),
                hot_items=Sum(
                    Case(
                        When(process_status__iexact='Hot', then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                )
            )
            .order_by('-revenue')
        )
        exec_labels = [e['visit__executive__username'] if e.get('visit__executive__username') else 'Unknown' for e in executive_performance]
        exec_revenue = [float(e['revenue'] or 0.0) for e in executive_performance]
        exec_conv_pct = [round(((e['hot_items'] or 0) / e['total_items'] * 100), 1) if e.get('total_items') else 0.0 for e in executive_performance]

        funnel_stages = (
            VisitedProductDetail.objects.filter(product_filters)
            .values('process_status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        funnel_list = [dict(stage) for stage in funnel_stages] if funnel_stages else []

        # 5. Maps & Telemetry
        geo_district_performance = (
            VisitedProductDetail.objects.filter(product_filters)
            .values('visit__farm__state', 'visit__farm__district')
            .annotate(
                farm_count=Count('visit__farm', distinct=True),
                revenue=Coalesce(Sum(Coalesce('revenue_generated', computed_rev)), 0.0, output_field=FloatField())
            )
            .order_by('-revenue')
        )
        map_labels = [d['visit__farm__district'] if d.get('visit__farm__district') else 'Unknown' for d in geo_district_performance[:10]]
        map_revenue = [float(d['revenue'] or 0.0) for d in geo_district_performance[:10]]

        telemetry_audit_log = (
            FarmVisitReport.objects.filter(visit_filters)
            .select_related('farm', 'executive')
            .values('visit_date', 'farm__area', 'farm__latitude', 'farm__longitude', 'executive__username', 'farm__farm_name')
            .order_by('-visit_date')[:15]
        )

        # 6. Demographics
        try:
            bird_population = FarmVisitReport.objects.filter(visit_filters).aggregate(
                chicks=Coalesce(Sum('farm__chicks_count'), 0),
                growers=Coalesce(Sum('farm__grower_count'), 0),
                layers=Coalesce(Sum('farm__layer_count'), 0),
                culling=Coalesce(Sum('farm__culling_bird_count'), 0)
            )
            if bird_population:
                bird_counts = [
                    (bird_population.get('chicks') or 0),
                    (bird_population.get('growers') or 0),
                    (bird_population.get('layers') or 0),
                    (bird_population.get('culling') or 0)
                ]
        except Exception as b_err:
            logger.warning(f"Bird count aggregation skipped: {b_err}")

        reported_problems = (
            FarmVisitReport.objects.filter(visit_filters)
            .values('farm_problem')
            .annotate(frequency=Count('id'))
            .exclude(farm_problem__in=['', None])
            .order_by('-frequency')[:10]
        )
        problems_list = [dict(prob) for prob in reported_problems] if reported_problems else []

        segment_breakdown = (
            Farm.objects.filter(farm_filters)
            .values('business_type', 'sub_segment')
            .annotate(total_farms=Count('id'))
            .order_by('-total_farms')
        )

        visit_frequency_exec = (
            FarmVisitReport.objects.filter(visit_filters)
            .values('executive__username')
            .annotate(visit_count=Count('id'))
            .order_by('-visit_count')
        )

        # 7. Trends
        month_wise_qs = list(
            VisitedProductDetail.objects.filter(product_filters)
            .annotate(month=TruncMonth('visit__visit_date'))
            .values('month')
            .annotate(revenue=Coalesce(Sum(Coalesce('revenue_generated', computed_rev)), 0.0, output_field=FloatField()))
            .filter(month__isnull=False)
            .order_by('month')
        )
        month_wise_labels = [m['month'].strftime("%b %Y") for m in month_wise_qs if m.get('month')]
        month_wise_data = [float(m['revenue'] or 0.0) for m in month_wise_qs]

        year_wise_qs = list(
            VisitedProductDetail.objects.filter(product_filters)
            .annotate(year=TruncYear('visit__visit_date'))
            .values('year')
            .annotate(revenue=Coalesce(Sum(Coalesce('revenue_generated', computed_rev)), 0.0, output_field=FloatField()))
            .filter(year__isnull=False)
            .order_by('year')
        )
        year_wise_labels = [y['year'].strftime("%Y") for y in year_wise_qs if y.get('year')]
        year_wise_data = [float(y['revenue'] or 0.0) for y in year_wise_qs]

        # 8. Table Display Mapping
        recent_visits_queryset = FarmVisitReport.objects.filter(
            visit_filters
        ).select_related('farm', 'executive').prefetch_related('visited_products').annotate(
            total_calculated_revenue=Coalesce(
                Sum(
                    ExpressionWrapper(
                        Coalesce(F('visited_products__sale_quantity'), 0) * Coalesce(F('visited_products__primary_price'), 0.0, output_field=FloatField()),
                        output_field=FloatField()
                    )
                ),
                0.0,
                output_field=FloatField()
            )
        ).order_by('-visit_date')[:10]

        state_list = Farm.objects.values_list('state', flat=True).distinct().exclude(state='')
        district_list = Farm.objects.values_list('district', flat=True).distinct().exclude(district='')
        executive_list = User.objects.filter(is_active=True).values_list('username', flat=True).distinct()

    except Exception as e:
        logger.error(f"Error computing get_dashboard_context: {str(e)}", exc_info=True)

    return {
        'total_revenue': total_rev,
        'total_visits': v_count,
        'active_executives': active_executives,
        'total_farms': total_farms_count,
        'total_sales_volume': vol_sold,
        'paid_orders_count': paid_orders_count,
        'avg_order_value': avg_order_value,
        'conversion_rate': conversion_rate,

        'hot_pct': hot_pct,
        'warm_pct': warm_pct,
        'cold_pct': cold_pct,
        'poultry_pct': poultry_pct,
        'aqua_pct': aqua_pct,

        'combo_labels_js': json.dumps(list(combo_labels), cls=DjangoJSONEncoder),
        'combo_revenue_js': json.dumps(list(combo_revenue), cls=DjangoJSONEncoder),
        'combo_volume_js': json.dumps(list(combo_volume), cls=DjangoJSONEncoder),
        'top_prod_labels_js': json.dumps(list(top_prod_labels), cls=DjangoJSONEncoder),
        'top_prod_revenue_js': json.dumps(list(top_prod_revenue), cls=DjangoJSONEncoder),
        'pipeline_spread': pipeline_spread,
        'product_pricing_table': product_pricing_table,

        'exec_labels_js': json.dumps(list(exec_labels), cls=DjangoJSONEncoder),
        'exec_revenue_js': json.dumps(list(exec_revenue), cls=DjangoJSONEncoder),
        'exec_conv_pct_js': json.dumps(list(exec_conv_pct), cls=DjangoJSONEncoder),
        'funnel_stages': funnel_stages,
        'funnel_stages_js': json.dumps(funnel_list, cls=DjangoJSONEncoder),

        'map_labels_js': json.dumps(list(map_labels), cls=DjangoJSONEncoder),
        'map_revenue_js': json.dumps(list(map_revenue), cls=DjangoJSONEncoder),
        'telemetry_audit_log': telemetry_audit_log,
        'geo_district_performance': geo_district_performance,

        'bird_labels_js': json.dumps(list(bird_labels), cls=DjangoJSONEncoder),
        'bird_counts_js': json.dumps(list(bird_counts), cls=DjangoJSONEncoder),
        'reported_problems': reported_problems,
        'reported_problems_js': json.dumps(problems_list, cls=DjangoJSONEncoder),
        'segment_breakdown': segment_breakdown,

        'visit_frequency_exec': visit_frequency_exec,
        
        'month_wise_cycle': month_wise_qs,
        'month_wise_labels_js': json.dumps(month_wise_labels, cls=DjangoJSONEncoder),
        'month_wise_data_js': json.dumps(month_wise_data, cls=DjangoJSONEncoder),
        
        'year_wise_trends': year_wise_qs,
        'year_wise_labels_js': json.dumps(year_wise_labels, cls=DjangoJSONEncoder),
        'year_wise_data_js': json.dumps(year_wise_data, cls=DjangoJSONEncoder),

        'recent_visits': recent_visits_queryset,

        'state_list': state_list,
        'district_list': district_list,
        'executive_list': executive_list,
        'country_list': ['India'],

        'selected_state': sel_state,
        'selected_country': sel_country,
        'selected_district': sel_district,
        'selected_executive': sel_executive,
        'selected_month': sel_month,
        'selected_year': sel_year,
    }


# ==========================================
# 🎯 SAFE CONTROLLER VIEWS (WITH FALLBACKS)
# ==========================================

@login_required(login_url='/crm/login/')
def dashboard_home(request):
    """Render Main Dashboard with template safe fallback"""
    templates = ['crm_core/dashboard.html', 'dashboard.html', 'crm_core/dashboard_home.html']
    try:
        context = get_dashboard_context(request)
        return render_safe(request, templates, context)
    except Exception as e:
        logger.error(f"Error rendering dashboard_home: {str(e)}", exc_info=True)
        messages.error(request, f"Unable to load dashboard: {str(e)}")
        return render_safe(request, templates, {})


@login_required(login_url='/crm/login/')
def dashboard_analytics(request):
    """Render Analytics Report dashboard with template safe fallback"""
    templates = ['crm_core/analytics_report.html', 'analytics_report.html', 'crm_core/analytics.html', 'analytics.html']
    try:
        context = get_dashboard_context(request)
        return render_safe(request, templates, context)
    except Exception as e:
        logger.error(f"Error rendering dashboard_analytics: {str(e)}", exc_info=True)
        messages.error(request, f"Unable to load analytics report: {str(e)}")
        return render_safe(request, templates, {})


@login_required(login_url='/crm/login/')
def executive_analytics_view(request):
    """Render Executive Analytics dashboard with template safe fallback"""
    templates = ['crm_core/executive_analytics.html', 'executive_analytics.html', 'crm_core/analytics_report.html']
    try:
        context = get_dashboard_context(request)
        return render_safe(request, templates, context)
    except Exception as e:
        logger.error(f"Error rendering executive_analytics_view: {str(e)}", exc_info=True)
        messages.error(request, f"Unable to load executive analytics: {str(e)}")
        return render_safe(request, templates, {})


# ==========================================
# 🛰️ GEOLOCATION & UTILITIES
# ==========================================

@login_required(login_url='/crm/login/')
def get_location_details(request):
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    return JsonResponse({'status': 'success', 'lat': lat, 'lng': lng})


# ==========================================
# 🛠️ DASHBOARD MAINTENANCE & ACTION VIEWS
# ==========================================

@login_required(login_url='/crm/login/')
def clear_dashboard_data(request):
    """Placeholder view to handle dashboard data clear requests safely."""
    messages.info(request, "Clear dashboard functionality is currently disabled.")
    return redirect('dashboard_home')

# =====================================================================
# 1. FORM SUBMISSION VIEW: Captures data from Field Visiting Log Form
# =====================================================================
@login_required
def submit_visit_log(request):
    """
    Handles POST requests from the 'MY AGRINUTRITION FIELD VISITING LOG' page.
    Saves Farm Profile, GPS Metrics, Diagnostics, Pipelines, and Orders.
    """
    if request.method == 'POST':
        try:
            # A. General Farm Profile & GPS Metrics
            farm_name = request.POST.get('farm_name', '').strip()
            owner_name = request.POST.get('owner_name', '').strip()
            contact_number = request.POST.get('contact_number', '').strip()
            
            district = request.POST.get('district', '').strip()
            area = request.POST.get('area', '').strip()
            state = request.POST.get('state', '').strip()
            latitude = request.POST.get('latitude', None)
            longitude = request.POST.get('longitude', None)

            # B. Diagnostic Metrics
            sector = request.POST.get('sector', '').strip()            # e.g. POULTRY / AQUA
            sub_sector = request.POST.get('sub_sector', '').strip()    # e.g. Broiler / Layer / Shrimp
            problem_observed = request.POST.get('problem_observed', '').strip()

            # C. Shed Inventory Counts
            chicks_count = int(request.POST.get('chicks_count', 0) or 0)
            grower_count = int(request.POST.get('grower_count', 0) or 0)
            layer_count = int(request.POST.get('layer_count', 0) or 0)
            culling_count = int(request.POST.get('culling_count', 0) or 0)

            # --- Create or Retrieve Farm Record ---
            farm_obj, _ = Farm.objects.get_or_create(
                name=farm_name if farm_name else "Unassigned Farm",
                defaults={'owner_name': owner_name, 'contact': contact_number}
            )

            # --- Create Main Visit Log Record ---
            visit = VisitLog.objects.create(
                executive=request.user,
                farm=farm_obj,
                farm_owner=owner_name,
                contact=contact_number,
                district=district,
                area=area,
                state=state,
                latitude=latitude if latitude else None,
                longitude=longitude if longitude else None,
                sector=sector,
                sub_sector=sub_sector,
                problem_observed=problem_observed,
                chicks_count=chicks_count,
                grower_count=grower_count,
                layer_count=layer_count,
                culling_count=culling_count
            )

            # D. Dynamic Pipeline Items Table
            pipe_products = request.POST.getlist('pipe_product_name[]')
            pipe_pot_qtys = request.POST.getlist('pipe_potential_qty[]')
            pipe_target_qtys = request.POST.getlist('pipe_target_qty[]')
            pipe_units = request.POST.getlist('pipe_units[]')
            pipe_stages = request.POST.getlist('pipe_stage[]')        # Hot / Warm / Cold
            pipe_convs = request.POST.getlist('pipe_conversion[]')

            for prod, pot_qty, tgt_qty, unit, stage, conv in zip(
                pipe_products, pipe_pot_qtys, pipe_target_qtys, pipe_units, pipe_stages, pipe_convs
            ):
                if prod.strip():
                    PipelineItem.objects.create(
                        visit=visit,
                        product_name=prod.strip(),
                        potential_qty=float(pot_qty or 0),
                        target_qty=float(tgt_qty or 0),
                        unit=unit,
                        stage=stage,
                        conversion_percentage=float(conv or 0)
                    )

            # E. Dynamic Confirmed Orders Table
            order_products = request.POST.getlist('order_product_name[]')
            order_qtys = request.POST.getlist('order_quantity[]')
            order_units = request.POST.getlist('order_units[]')
            order_rates = request.POST.getlist('order_rate[]')

            for prod, qty, unit, rate in zip(order_products, order_qtys, order_units, order_rates):
                num_qty = float(qty or 0)
                num_rate = float(rate or 0)
                if prod.strip() and num_qty > 0:
                    OrderItem.objects.create(
                        visit=visit,
                        product_name=prod.strip(),
                        quantity=num_qty,
                        unit=unit,
                        rate=num_rate,
                        total_amount=num_qty * num_rate
                    )

            messages.success(request, f"Visit entry for '{farm_obj.name}' saved successfully!")
            return redirect('analytics_dashboard')

        except Exception as e:
            messages.error(request, f"Error saving visit log: {str(e)}")
            return redirect('submit_visit_log')

    # GET Request: Display form
    return render(request, 'field_log_form.html')


# =====================================================================
# 2. DASHBOARD VIEW: Processes & Aggregates Data for Chart.js
# =====================================================================
def analytics_dashboard(request):
    """
    Queries submitted VisitLogs, OrderItems, and PipelineItems,
    aggregates metrics, and passes serialized JSON data for live charts.
    """
    # --- Form Filters (Executive, Date Range, Sector) ---
    selected_exec = request.GET.get('executive', 'ALL')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    selected_sector = request.GET.get('sector', 'ALL')

    # Base Querysets
    visits_qs = VisitLog.objects.all().select_related('executive', 'farm')
    orders_qs = OrderItem.objects.all().select_related('visit')
    pipeline_qs = PipelineItem.objects.all().select_related('visit')

    # Apply Filters
    if selected_exec != 'ALL' and selected_exec.isdigit():
        visits_qs = visits_qs.filter(executive_id=int(selected_exec))
        orders_qs = orders_qs.filter(visit__executive_id=int(selected_exec))
        pipeline_qs = pipeline_qs.filter(visit__executive_id=int(selected_exec))

    if start_date:
        visits_qs = visits_qs.filter(visit_date__gte=start_date)
        orders_qs = orders_qs.filter(visit__visit_date__gte=start_date)
        pipeline_qs = pipeline_qs.filter(visit__visit_date__gte=start_date)

    if end_date:
        visits_qs = visits_qs.filter(visit_date__lte=end_date)
        orders_qs = orders_qs.filter(visit__visit_date__lte=end_date)
        pipeline_qs = pipeline_qs.filter(visit__visit_date__lte=end_date)

    if selected_sector != 'ALL':
        visits_qs = visits_qs.filter(sector__iexact=selected_sector)
        orders_qs = orders_qs.filter(visit__sector__iexact=selected_sector)
        pipeline_qs = pipeline_qs.filter(visit__sector__iexact=selected_sector)

    # -----------------------------------------------------------------
    # 📊 KPI DECK CALCULATIONS
    # -----------------------------------------------------------------
    total_visits = visits_qs.count()
    total_executives = visits_qs.values('executive').distinct().count()
    total_farms = visits_qs.values('farm').distinct().count()
    
    total_qty = orders_qs.aggregate(sum_qty=Sum('quantity'))['sum_qty'] or 0
    total_revenue_val = orders_qs.aggregate(sum_rev=Sum('total_amount'))['sum_rev'] or 0.0
    
    avg_revenue_val = (total_revenue_val / total_visits) if total_visits > 0 else 0.0

    # Format Currency Values
    total_revenue_str = f"{total_revenue_val:,.2f}"
    avg_revenue_str = f"{avg_revenue_val:,.2f}"

    # -----------------------------------------------------------------
    # 📈 CHART 1: MONTH-WISE REVENUE REVIEW
    # -----------------------------------------------------------------
    monthly_data = (
        orders_qs.annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Sum('total_amount'))
        .order_by('month')
    )
    month_labels = [d['month'].strftime('%b %Y') for d in monthly_data if d['month']]
    month_values = [float(d['total']) for d in monthly_data if d['month']]

    # -----------------------------------------------------------------
    # 📈 CHART 2: YEAR-WISE REVENUE REVIEW
    # -----------------------------------------------------------------
    yearly_data = (
        orders_qs.annotate(year=TruncYear('created_at'))
        .values('year')
        .annotate(total=Sum('total_amount'))
        .order_by('year')
    )
    year_labels = [str(d['year'].year) for d in yearly_data if d['year']]
    year_values = [float(d['total']) for d in yearly_data if d['year']]

    # -----------------------------------------------------------------
    # 📊 CHART 3: REVENUE BY EXECUTIVE
    # -----------------------------------------------------------------
    exec_data = (
        orders_qs.values('visit__executive__first_name', 'visit__executive__username')
        .annotate(total=Sum('total_amount'))
        .order_by('-total')
    )
    exec_labels = [
        d['visit__executive__first_name'] or d['visit__executive__username'] or "Unknown"
        for d in exec_data
    ]
    exec_values = [float(d['total']) for d in exec_data]

    # -----------------------------------------------------------------
    # 🍩 CHART 4: PRODUCT ALLOCATION (ORDER VOLUME)
    # -----------------------------------------------------------------
    prod_data = (
        orders_qs.values('product_name')
        .annotate(total_vol=Sum('quantity'))
        .order_by('-total_vol')[:6]
    )
    prod_labels = [d['product_name'] for d in prod_data]
    prod_values = [float(d['total_vol']) for d in prod_data]

    # -----------------------------------------------------------------
    # 🗺️ CHART 5: VISITS BY STATE
    # -----------------------------------------------------------------
    state_data = (
        visits_qs.values('state')
        .annotate(total_visits=Count('id'))
        .order_by('-total_visits')[:6]
    )
    state_labels = [d['state'] if d['state'] else "Unassigned" for d in state_data]
    state_values = [d['total_visits'] for d in state_data]

    # -----------------------------------------------------------------
    # 🔬 CHART 6: FIELD PROBLEMS OBSERVED
    # -----------------------------------------------------------------
    prob_data = (
        visits_qs.exclude(problem_observed='')
        .values('problem_observed')
        .annotate(prob_count=Count('id'))
        .order_by('-prob_count')[:5]
    )
    prob_labels = [d['problem_observed'] for d in prob_data]
    prob_values = [d['prob_count'] for d in prob_data]

    # -----------------------------------------------------------------
    # 🌡️ PIPELINE TEMPERATURE % METRICS
    # -----------------------------------------------------------------
    total_pipe_items = pipeline_qs.count() or 1
    hot_count = pipeline_qs.filter(stage__iexact='Hot').count()
    warm_count = pipeline_qs.filter(stage__iexact='Warm').count()
    cold_count = pipeline_qs.filter(stage__iexact='Cold').count()

    pipeline_hot = round((hot_count / total_pipe_items) * 100)
    pipeline_warm = round((warm_count / total_pipe_items) * 100)
    pipeline_cold = round((cold_count / total_pipe_items) * 100)

    # -----------------------------------------------------------------
    # 🐓/🐟 SECTOR DISTRIBUTION % METRICS
    # -----------------------------------------------------------------
    total_sector_visits = visits_qs.count() or 1
    poultry_count = visits_qs.filter(sector__iexact='POULTRY').count()
    aqua_count = visits_qs.filter(sector__iexact='AQUA').count()

    sector_poultry_pct = round((poultry_count / total_sector_visits) * 100)
    sector_aqua_pct = round((aqua_count / total_sector_visits) * 100)

    # -----------------------------------------------------------------
    # 🏆 TOP FARMS BY BOOKING REVENUE & RECENT VISITS LEDGER
    # -----------------------------------------------------------------
    top_farms = (
        orders_qs.values('visit__farm__name')
        .annotate(revenue=Sum('total_amount'))
        .order_by('-revenue')[:5]
    )
    top_farms_list = [
        {'name': item['visit__farm__name'] or 'Unnamed Farm', 'revenue': f"{item['revenue']:,.2f}"}
        for item in top_farms
    ]

    recent_visits = visits_qs.order_by('-created_at')[:10]

    # -----------------------------------------------------------------
    # 📦 CONTEXT DICTIONARY
    # -----------------------------------------------------------------
    context = {
        # Dropdown options
        'executives_list': Executive.objects.all(),
        'selected_executive': selected_exec,
        'start_date': start_date,
        'end_date': end_date,
        'selected_sector': selected_sector,

        # Top KPIs
        'total_visits': total_visits,
        'total_executives': total_executives,
        'total_farms': total_farms,
        'total_qty': f"{total_qty:,.0f}",
        'total_revenue': total_revenue_str,
        'avg_revenue': avg_revenue_str,

        # Serialized JSON string arrays for JavaScript Chart rendering
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
        
        'problem_labels_json': json.dumps(prob_labels),
        'problem_data_json': json.dumps(prob_values),

        # Pipeline & Sector Percentages
        'pipeline_hot': pipeline_hot,
        'pipeline_warm': pipeline_warm,
        'pipeline_cold': pipeline_cold,
        'sector_poultry_pct': sector_poultry_pct,
        'sector_aqua_pct': sector_aqua_pct,

        # Table Ledgers
        'top_farms': top_farms_list,
        'recent_visits': recent_visits,
    }

    return render(request, 'dashboard.html', context)

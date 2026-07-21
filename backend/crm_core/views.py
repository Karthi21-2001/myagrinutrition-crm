import csv
import json
import logging
import openpyxl
import requests
import traceback

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Avg, Count, DecimalField, F, Q, Sum
from django.db.models.functions import TruncMonth, TruncYear
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .forms import ExecutiveSignUpForm
from .models import Farm, FarmVisitReport, VisitedProductDetail

logger = logging.getLogger(__name__)
User = get_user_model()


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
    return render(request, 'crm_core/register.html', {'form': form})


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
    return render(request, 'crm_core/login.html', {'form': form})


def logout_user(request):
    logout(request)
    return redirect('login_user')


# ==========================================
# 🌱 AGRI-CORE MANAGEMENT FUNCTIONALITY
# ==========================================

@login_required(login_url='/crm/login/')
def render_visit_form(request):
    return render(request, 'crm_core/farm_visit_form.html')


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

            return render(request, 'crm_core/farm_visit_form.html', {'saved_data': request.POST})

        except Exception as e:
            logger.error(f"Error in save_farm_visit: {str(e)}", exc_info=True)
            messages.error(request, f"Database transaction block failed: {str(e)}")
            return render(request, 'crm_core/farm_visit_form.html', {'saved_data': request.POST})

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
    ).order_by('-visit_date')

    current_row = 2
    for v in all_visits:
        f = v.farm if v else None
        products = VisitedProductDetail.objects.filter(visit=v)
        product_loop_list = products if products.exists() else [None]

        for p in product_loop_list:
            ws_data.cell(row=current_row, column=1, value=v.visit_date.strftime("%Y-%m-%d %H:%M") if v and v.visit_date else "")
            ws_data.cell(row=current_row, column=2, value=v.executive.username if v and v.executive else "")
            ws_data.cell(row=current_row, column=3, value=f.farm_name if f else "")
            ws_data.cell(row=current_row, column=4, value=f.owner_name if f else "")
            ws_data.cell(row=current_row, column=5, value=f.contact_number if f else "")
            ws_data.cell(row=current_row, column=6, value=f.business_type if f else "")
            ws_data.cell(row=current_row, column=7, value=f.sub_segment if (f and f.sub_segment) else "") 
            ws_data.cell(row=current_row, column=8, value=f.state if f else "")
            ws_data.cell(row=current_row, column=9, value=f.district if f else "")
            ws_data.cell(row=current_row, column=10, value=f.area if f else "")

            ws_data.cell(row=current_row, column=11, value=v.farm_problem if (v and v.farm_problem) else "None reported")
            
            ws_data.cell(row=current_row, column=12, value=getattr(v, 'chicks_count', 0))
            ws_data.cell(row=current_row, column=13, value=getattr(v, 'grower_count', 0))
            ws_data.cell(row=current_row, column=14, value=getattr(v, 'layer_count', 0))
            ws_data.cell(row=current_row, column=15, value=getattr(v, 'culling_bird', 0))

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
    """Computes all KPI aggregates, Chart data series, and list structures

    for the MyAgriNutrition Analytics Dashboard.
    """
    # ------------------------------------------------------------------
    # 1. READ FILTER INPUTS FROM REQUEST
    # ------------------------------------------------------------------
    sel_state = request.GET.get("state", "").strip()
    sel_country = request.GET.get("country", "").strip()
    sel_district = request.GET.get("district", "").strip()
    sel_executive = request.GET.get("executive", "").strip()
    sel_month = request.GET.get("month", "").strip()
    sel_year = request.GET.get("year", "").strip()
    sel_sector = request.GET.get("sector", "").strip()

    # ------------------------------------------------------------------
    # 2. CONSTRUCT FILTER CONDITIONS
    # ------------------------------------------------------------------
    farm_filters = Q()
    visit_filters = Q()
    product_filters = Q()

    # Geographic Filters
    if sel_state and sel_state not in ["All", "All States", ""]:
        farm_filters &= Q(state__iexact=sel_state)
        visit_filters &= Q(farm__state__iexact=sel_state)
        product_filters &= Q(visit__farm__state__iexact=sel_state)

    if sel_district and sel_district not in ["All", "All Districts", ""]:
        farm_filters &= Q(district__iexact=sel_district)
        visit_filters &= Q(farm__district__iexact=sel_district)
        product_filters &= Q(visit__farm__district__iexact=sel_district)

    # Executive Filters
    if sel_executive and sel_executive not in ["All", "All Executives", ""]:
        farm_filters &= Q(executive__username__iexact=sel_executive)
        visit_filters &= Q(executive__username__iexact=sel_executive)
        product_filters &= Q(visit__executive__username__iexact=sel_executive)

    # Date Filters (Month / Year)
    if sel_month and sel_month not in ["All", "All Months", ""]:
        try:
            m_val = int(sel_month)
            visit_filters &= Q(visit_date__month=m_val)
            product_filters &= Q(visit__visit_date__month=m_val)
        except ValueError:
            pass

    if sel_year and sel_year not in ["All", ""]:
        try:
            y_val = int(sel_year)
            visit_filters &= Q(visit_date__year=y_val)
            product_filters &= Q(visit__visit_date__year=y_val)
        except ValueError:
            pass

    # Sector Filter
    if sel_sector and sel_sector not in ["All", "All Sectors", ""]:
        farm_filters &= Q(business_type__icontains=sel_sector)
        visit_filters &= Q(farm__business_type__icontains=sel_sector)
        product_filters &= Q(visit__farm__business_type__icontains=sel_sector)

    # ------------------------------------------------------------------
    # 3. BASE QUERYSETS
    # ------------------------------------------------------------------
    visit_qs = FarmVisitReport.objects.filter(visit_filters)
    farm_qs = Farm.objects.filter(farm_filters)
    product_qs = VisitedProductDetail.objects.filter(product_filters)

    # Fallback check: If product_qs is empty, fallback to visit_qs for primary KPIs
    has_product_records = product_qs.exists()

    # ------------------------------------------------------------------
    # 4. PRIMARY METRICS ACCUMULATION
    # ------------------------------------------------------------------
    v_count = visit_qs.count()
    total_farms_count = farm_qs.count()

    # Unique Active Executives logging visits
    active_execs_qs = (
        visit_qs.exclude(Q(executive__isnull=True) | Q(executive__username=""))
        .values("executive")
        .distinct()
    )
    active_executives = active_execs_qs.count()

    # Financial Aggregations with Coalesce Protection
    total_rev = float(
        product_qs.aggregate(total=Coalesce(Sum("revenue_generated"), 0.0))[
            "total"
        ]
    )

    vol_sold = int(
        product_qs.aggregate(total_qty=Coalesce(Sum("sale_quantity"), 0))[
            "total_qty"
        ]
    )

    paid_orders_count = product_qs.filter(
        Q(sale_quantity__gt=0) | Q(revenue_generated__gt=0)
    ).count()

    avg_order_value = (
        float(total_rev / paid_orders_count) if paid_orders_count > 0 else 0.0
    )

    # Sector Breakdown Percentages
    poultry_pct, aqua_pct = 0.0, 0.0
    if total_farms_count > 0:
        p_cnt = farm_qs.filter(business_type__icontains="Poultry").count()
        a_cnt = farm_qs.filter(business_type__icontains="Aqua").count()
        poultry_pct = round((p_cnt / total_farms_count) * 100, 1)
        aqua_pct = round((a_cnt / total_farms_count) * 100, 1)

    # Lead Temperature / Pipeline Conversions
    total_leads = product_qs.count()
    hot_pct, warm_pct, cold_pct = 0.0, 0.0, 0.0
    if total_leads > 0:
        h_cnt = product_qs.filter(process_status__iexact="Hot").count()
        w_cnt = product_qs.filter(process_status__iexact="Warm").count()
        c_cnt = product_qs.filter(process_status__iexact="Cold").count()

        hot_pct = round((h_cnt / total_leads) * 100, 1)
        warm_pct = round((w_cnt / total_leads) * 100, 1)
        cold_pct = round((c_cnt / total_leads) * 100, 1)

    conversion_rate = hot_pct

    # ------------------------------------------------------------------
    # 5. CHART DATA SERIES GENERATION (SAFE JSON MATRICES)
    # ------------------------------------------------------------------

    # Chart 1: Month-Wise Revenue & Trends
    month_wise_qs = list(
        product_qs.annotate(month=TruncMonth("visit__visit_date"))
        .values("month")
        .annotate(revenue=Coalesce(Sum("revenue_generated"), 0.0))
        .filter(month__isnull=False)
        .order_by("month")
    )
    month_wise_labels = [
        m["month"].strftime("%b %Y") for m in month_wise_qs if m.get("month")
    ]
    month_wise_data = [float(m["revenue"]) for m in month_wise_qs]

    # Chart 2: Year-Wise Revenue
    year_wise_qs = list(
        product_qs.annotate(year=TruncYear("visit__visit_date"))
        .values("year")
        .annotate(revenue=Coalesce(Sum("revenue_generated"), 0.0))
        .filter(year__isnull=False)
        .order_by("year")
    )
    year_wise_labels = [
        y["year"].strftime("%Y") for y in year_wise_qs if y.get("year")
    ]
    year_wise_data = [float(y["revenue"]) for y in year_wise_qs]

    # Chart 3: Executive Performance Breakdown
    exec_perf = (
        product_qs.values("visit__executive__username")
        .annotate(
            revenue=Coalesce(Sum("revenue_generated"), 0.0),
            total_items=Count("id"),
            hot_items=Count("id", filter=Q(process_status__iexact="Hot")),
        )
        .order_by("-revenue")[:10]
    )
    exec_labels = [
        e["visit__executive__username"] or "Unassigned" for e in exec_perf
    ]
    exec_revenue = [float(e["revenue"]) for e in exec_perf]
    exec_conv_pct = [
        round((e["hot_items"] / e["total_items"] * 100), 1)
        if e["total_items"] > 0
        else 0.0
        for e in exec_perf
    ]

    # Chart 4: Product Allocation / Volume
    prod_perf = (
        product_qs.values("product_name")
        .annotate(
            revenue=Coalesce(Sum("revenue_generated"), 0.0),
            qty_sold=Coalesce(Sum("sale_quantity"), 0),
        )
        .exclude(Q(product_name__isnull=True) | Q(product_name=""))
        .order_by("-qty_sold")[:6]
    )
    top_prod_labels = [p["product_name"] for p in prod_perf]
    top_prod_revenue = [float(p["revenue"]) for p in prod_perf]

    # Chart 5: Visits By State
    state_qs = (
        visit_qs.values("farm__state")
        .annotate(total_visits=Count("id"))
        .exclude(Q(farm__state__isnull=True) | Q(farm__state=""))
        .order_by("-total_visits")[:6]
    )
    state_labels = [s["farm__state"] for s in state_qs]
    state_data = [s["total_visits"] for s in state_qs]

    # Chart 6: Field Problems Observed
    prob_qs = (
        visit_qs.values("farm_problem")
        .annotate(frequency=Count("id"))
        .exclude(Q(farm_problem__isnull=True) | Q(farm_problem=""))
        .order_by("-frequency")[:5]
    )
    prob_labels = [p["farm_problem"] for p in prob_qs]
    prob_data = [p["frequency"] for p in prob_qs]

  # ------------------------------------------------------------------
    # 6. DEMOGRAPHICS, MAPS & LIST DATA
    # ------------------------------------------------------------------

    # Top Farms Table by Revenue
    try:
        top_farms_table = (
            product_qs.values(
                "visit__farm__farm_name", "visit__farm__owner_name"
            )
            .annotate(revenue=Coalesce(Sum("revenue_generated"), 0.0))
            .filter(revenue__gt=0)
            .order_by("-revenue")[:5]
        )
    except Exception as e:
        logger.warning(f"Top farms table aggregation skipped: {e}")
        top_farms_table = []

    # Bird Population Aggregates (Wrapped defensively to prevent missing field crashes)
    try:
        bird_population = visit_qs.aggregate(
            chicks=Coalesce(Sum("chicks_count"), 0),
            growers=Coalesce(Sum("grower_count"), 0),
            layers=Coalesce(Sum("layer_count"), 0),
            culling=Coalesce(Sum("culling_bird"), 0),
        )
        bird_counts = [
            bird_population["chicks"],
            bird_population["growers"],
            bird_population["layers"],
            bird_population["culling"],
        ]
    except Exception as e:
        logger.warning(f"Bird count aggregation skipped: {e}")
        bird_counts = [0, 0, 0, 0]

    bird_labels = ["Chicks", "Growers", "Layers", "Culling Birds"]

    # Pipeline Quantities
    try:
        pipeline_spread_agg = product_qs.aggregate(
            actual=Coalesce(Sum("sale_quantity"), 0),
            target=Coalesce(Sum("target_quantity"), 0),
            potential=Coalesce(Sum("potential_quantity"), 0),
        )
    except Exception as e:
        logger.warning(f"Pipeline spread aggregation skipped: {e}")
        pipeline_spread_agg = {"actual": 0, "target": 0, "potential": 0}

    # Recent Visit Activity Feed
    recent_visits = visit_qs.select_related("farm", "executive").order_by(
        "-visit_date"
    )[:10]

    # Filter Options Dynamic Querying
    state_list = list(
        Farm.objects.exclude(Q(state__isnull=True) | Q(state=""))
        .values_list("state", flat=True)
        .distinct()
    )
    district_list = list(
        Farm.objects.exclude(Q(district__isnull=True) | Q(district=""))
        .values_list("district", flat=True)
        .distinct()
    )
    executive_list = list(
        User.objects.filter(is_active=True)
        .values_list("username", flat=True)
        .distinct()
    )

    # ------------------------------------------------------------------
    # 7. ASSEMBLE CONTEXT
    # ------------------------------------------------------------------
    return {
        # Primary Numeric KPIs
        "total_revenue": total_rev,
        "total_visits": v_count,
        "active_executives": active_executives,
        "total_farms": total_farms_count,
        "total_sales_volume": vol_sold,
        "paid_orders_count": paid_orders_count,
        "avg_order_value": avg_order_value,
        "conversion_rate": conversion_rate,
        # Metrics Percentages
        "hot_pct": hot_pct,
        "warm_pct": warm_pct,
        "cold_pct": cold_pct,
        "poultry_pct": poultry_pct,
        "aqua_pct": aqua_pct,
        # Pre-Serialized Safe JSON Data for Chart.js
        "month_wise_labels_js": json.dumps(
            month_wise_labels, cls=DjangoJSONEncoder
        ),
        "month_wise_data_js": json.dumps(
            month_wise_data, cls=DjangoJSONEncoder
        ),
        "year_wise_labels_js": json.dumps(
            year_wise_labels, cls=DjangoJSONEncoder
        ),
        "year_wise_data_js": json.dumps(year_wise_data, cls=DjangoJSONEncoder),
        "exec_labels_js": json.dumps(exec_labels, cls=DjangoJSONEncoder),
        "exec_revenue_js": json.dumps(exec_revenue, cls=DjangoJSONEncoder),
        "exec_conv_pct_js": json.dumps(exec_conv_pct, cls=DjangoJSONEncoder),
        "top_prod_labels_js": json.dumps(
            top_prod_labels, cls=DjangoJSONEncoder
        ),
        "top_prod_revenue_js": json.dumps(
            top_prod_revenue, cls=DjangoJSONEncoder
        ),
        "state_labels_js": json.dumps(state_labels, cls=DjangoJSONEncoder),
        "state_data_js": json.dumps(state_data, cls=DjangoJSONEncoder),
        "prob_labels_js": json.dumps(prob_labels, cls=DjangoJSONEncoder),
        "prob_data_js": json.dumps(prob_data, cls=DjangoJSONEncoder),
        "bird_labels_js": json.dumps(bird_labels, cls=DjangoJSONEncoder),
        "bird_counts_js": json.dumps(bird_counts, cls=DjangoJSONEncoder),
        # Structured Tables & Querysets
        "pipeline_spread": pipeline_spread_agg,
        "top_farms": top_farms_table,
        "recent_visits": recent_visits,
        # Dropdown Options
        "state_list": state_list,
        "district_list": district_list,
        "executive_list": executive_list,
        "country_list": ["India"],
        # Filter State Retention
        "selected_state": sel_state,
        "selected_country": sel_country,
        "selected_district": sel_district,
        "selected_executive": sel_executive,
        "selected_month": sel_month,
        "selected_year": sel_year,
        "selected_sector": sel_sector,
    }

def dashboard_view(request):
    """View handler that renders the context into the HTML template."""
    context = get_dashboard_context(request)
    return render(request, 'dashboard.html', context)


@login_required(login_url='/crm/login/')
def dashboard_home(request):
    context = get_dashboard_context(request)
    return render(request, 'crm_core/dashboard.html', context)


@login_required(login_url='/crm/login/')
def dashboard_analytics(request):
    context = get_dashboard_context(request)
    return render(request, 'crm_core/analytics_report.html', context)


@login_required(login_url='/crm/login/')
def executive_analytics_view(request):
    context = get_dashboard_context(request)
    return render(request, 'crm_core/analytics_report.html', context)

@login_required(login_url='/crm/login/')
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def clear_dashboard_data(request):
    """
    Clears all farm visit, product detail, and farm records from the CRM.
    Restricted to superusers/staff.
    """
    if request.method == 'POST':
        try:
            with transaction.atomic():
                VisitedProductDetail.objects.all().delete()
                FarmVisitReport.objects.all().delete()
                Farm.objects.all().delete()
            messages.success(request, "Dashboard data cleared successfully!")
        except Exception as e:
            logger.error(f"Failed to clear dashboard data: {str(e)}")
            messages.error(request, f"Error clearing data: {str(e)}")
    return redirect('dashboard_home')

# Place these at the end of backend/crm_core/views.py

@login_required(login_url='/crm/login/')
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def clear_dashboard_data(request):
    """
    Clears all farm visit, product detail, and farm records from the CRM.
    Restricted to superusers/staff.
    """
    if request.method == 'POST':
        try:
            with transaction.atomic():
                VisitedProductDetail.objects.all().delete()
                FarmVisitReport.objects.all().delete()
                Farm.objects.all().delete()
            messages.success(request, "Dashboard data cleared successfully!")
        except Exception as e:
            logger.error(f"Failed to clear dashboard data: {str(e)}")
            messages.error(request, f"Error clearing data: {str(e)}")
    return redirect('dashboard_home')


@login_required(login_url='/crm/login/')
def get_location_details(request):
    """
    API endpoint for reverse geocoding latitude and longitude into location details.
    """
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')

    if not lat or not lon:
        return JsonResponse({'error': 'Latitude and longitude required.'}, status=400)

    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
        headers = {'User-Agent': 'AgriNutritionCRM/1.0'}
        res = requests.get(url, headers=headers, timeout=5)
        
        if res.status_code == 200:
            data = res.json()
            address = data.get('address', {})
            return JsonResponse({
                'state': address.get('state', ''),
                'district': address.get('state_district') or address.get('county') or address.get('district', ''),
                'area': address.get('suburb') or address.get('village') or address.get('town') or address.get('city', '')
            })
        return JsonResponse({'error': 'Failed to fetch location data.'}, status=500)
    except Exception as e:
        logger.error(f"Geocoding error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

import csv
import json
import requests
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Sum, Count, F, DecimalField, Q
from django.db.models.functions import TruncMonth, TruncYear
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from .models import Farm, FarmVisitReport, VisitedProductDetail
from .forms import ExecutiveSignUpForm 

User = get_user_model()

# ==========================================
# 📥 EXCEL EXPORT ENGINE
# ==========================================

@csrf_exempt
def export_visits_to_excel(request):
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()
    executive_filter = request.GET.get('executive', 'All').strip()
    state_filter = request.GET.get('state', 'All').strip()
    district_filter = request.GET.get('district', 'All').strip()
    business_type = request.GET.get('business_type', 'All').strip()
    sub_segment_filter = request.GET.get('sub_segment', 'All').strip()

    export_filters = Q()

    if business_type and business_type != 'All':
        export_filters &= Q(visit__farm__business_type__iexact=business_type)
    if sub_segment_filter and sub_segment_filter != 'All':
        export_filters &= Q(visit__farm__sub_segment__iexact=sub_segment_filter)
    if state_filter and state_filter != 'All':
        export_filters &= Q(visit__farm__state__iexact=state_filter)
    if district_filter and district_filter != 'All':
        export_filters &= Q(visit__farm__district__iexact=district_filter)
    if executive_filter and executive_filter != 'All':
        export_filters &= Q(visit__executive__username__iexact=executive_filter)

    if start_date_str:
        try:
            export_filters &= Q(visit__visit_date__date__gte=start_date_str)
        except ValueError:
            pass
    if end_date_str:
        try:
            export_filters &= Q(visit__visit_date__date__lte=end_date_str)
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

    # 🟢 ADDED 'Live GPS Link' TO HEADERS
    headers = [
        'Visit Date', 'Executive Name', 'Farm Name', 'Owner Name', 'Contact Number', 
        'Sector Segment', 'Sub-Segment', 'State', 'District', 'Area / Suburb', 
        'Product Name', 'Sale Qty', 'Price (INR)', 'Revenue Generated', 'Live GPS Link'
    ]

    for col_idx, text in enumerate(headers, 1):
        cell = ws_data.cell(row=1, column=col_idx, value=text)
        cell.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color=dark_slate, end_color=dark_slate, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws_data.row_dimensions[1].height = 28

    all_products = VisitedProductDetail.objects.filter(export_filters).select_related(
        'visit__farm', 'visit__executive'
    ).order_by('-visit__visit_date')
    
    current_row = 2
    for p in all_products:
        v = p.visit
        f = v.farm if v else None
        
        ws_data.cell(row=current_row, column=1, value=v.visit_date.strftime("%Y-%m-%d %H:%M") if v and v.visit_date else "")
        ws_data.cell(row=current_row, column=2, value=v.executive.username if v and v.executive else "")
        ws_data.cell(row=current_row, column=3, value=f.farm_name if f else "")
        ws_data.cell(row=current_row, column=4, value=f.owner_name if f else "")
        ws_data.cell(row=current_row, column=5, value=f.contact_number if f else "")
        ws_data.cell(row=current_row, column=6, value=f.business_type if f else "")
        ws_data.cell(row=current_row, column=7, value=f.sub_segment if f and f.sub_segment else "") 
        ws_data.cell(row=current_row, column=8, value=f.state if f else "")
        ws_data.cell(row=current_row, column=9, value=f.district if f else "")
        ws_data.cell(row=current_row, column=10, value=f.area if f else "")
        ws_data.cell(row=current_row, column=11, value=p.product_name)
        ws_data.cell(row=current_row, column=12, value=p.sale_quantity)
        ws_data.cell(row=current_row, column=13, value=float(p.primary_price))
        ws_data.cell(row=current_row, column=14, value=float(p.revenue_generated))
        
        # 🟢 GENERATING DYNAMIC HYPERLINK IF COORDINATES EXIST
        gps_cell = ws_data.cell(row=current_row, column=15)
        if f and f.latitude and f.longitude:
            gps_cell.value = "View on Map"
            gps_cell.hyperlink = f"https://maps.google.com/?q={f.latitude},{f.longitude}"
            gps_cell.font = Font(name="Segoe UI", size=11, color="0000FF", underline="single")
        else:
            gps_cell.value = "No GPS Data"
            gps_cell.font = Font(name="Segoe UI", size=11, color="64748B", italic=True)

        # Updated loop index from 1..15 to apply borders to the new column as well
        for c_idx in range(1, 16):
            ws_data.cell(row=current_row, column=c_idx).border = thin_border
        current_row += 1

    for col in ws_data.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_data.column_dimensions[col_letter].width = max(max_len + 4, 15)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="MyAgrinutrition_CRM_Field_Logs.xlsx"'
    wb.save(response)
    return response


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
        sub_segment = request.POST.get('sub_segment', '').strip() 
        
        district = request.POST.get('district', '').strip()
        area = request.POST.get('area', '').strip()
        farm_problem = request.POST.get('farm_problem')
        
        state = request.POST.get('state', '').strip()
        if not state or state.lower() == 'state':
            state = district if district else 'Unknown State'
        
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
                    defaults={
                        'executive': current_user,
                        'contact_number': contact_number,
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

                # Orders Processing Segment
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

                # Future Deal Target Segment
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
    executive_filter = request.GET.get('executive', 'All').strip()
    state_filter = request.GET.get('state', 'All').strip()
    district_filter = request.GET.get('district', 'All').strip()
    business_type = request.GET.get('business_type', 'All').strip()
    sub_segment_filter = request.GET.get('sub_segment', 'All').strip()

    export_filters = Q()

    if business_type and business_type != 'All':
        export_filters &= Q(visit__farm__business_type__iexact=business_type)
    if sub_segment_filter and sub_segment_filter != 'All':
        export_filters &= Q(visit__farm__sub_segment__iexact=sub_segment_filter)
    if state_filter and state_filter != 'All':
        export_filters &= Q(visit__farm__state__iexact=state_filter)
    if district_filter and district_filter != 'All':
        export_filters &= Q(visit__farm__district__iexact=district_filter)
    if executive_filter and executive_filter != 'All':
        export_filters &= Q(visit__executive__username__iexact=executive_filter)

    if start_date_str:
        try:
            export_filters &= Q(visit__visit_date__date__gte=start_date_str)
        except ValueError:
            pass
    if end_date_str:
        try:
            export_filters &= Q(visit__visit_date__date__lte=end_date_str)
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
        'Product Name', 'Sale Qty', 'Price (INR)', 'Revenue Generated'
    ]

    for col_idx, text in enumerate(headers, 1):
        cell = ws_data.cell(row=1, column=col_idx, value=text)
        cell.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color=dark_slate, end_color=dark_slate, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws_data.row_dimensions[1].height = 28

    all_products = VisitedProductDetail.objects.filter(export_filters).select_related(
        'visit__farm', 'visit__executive'
    ).order_by('-visit__visit_date')
    
    current_row = 2
    for p in all_products:
        v = p.visit
        f = v.farm if v else None
        
        ws_data.cell(row=current_row, column=1, value=v.visit_date.strftime("%Y-%m-%d %H:%M") if v and v.visit_date else "")
        ws_data.cell(row=current_row, column=2, value=v.executive.username if v and v.executive else "")
        ws_data.cell(row=current_row, column=3, value=f.farm_name if f else "")
        ws_data.cell(row=current_row, column=4, value=f.owner_name if f else "")
        ws_data.cell(row=current_row, column=5, value=f.contact_number if f else "")
        ws_data.cell(row=current_row, column=6, value=f.business_type if f else "")
        ws_data.cell(row=current_row, column=7, value=f.sub_segment if f and f.sub_segment else "") 
        ws_data.cell(row=current_row, column=8, value=f.state if f else "")
        ws_data.cell(row=current_row, column=9, value=f.district if f else "")
        ws_data.cell(row=current_row, column=10, value=f.area if f else "")
        ws_data.cell(row=current_row, column=11, value=p.product_name)
        ws_data.cell(row=current_row, column=12, value=p.sale_quantity)
        ws_data.cell(row=current_row, column=13, value=float(p.primary_price))
        ws_data.cell(row=current_row, column=14, value=float(p.revenue_generated))
        
        for c_idx in range(1, 15):
            ws_data.cell(row=current_row, column=c_idx).border = thin_border
        current_row += 1

    for col in ws_data.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_data.column_dimensions[col_letter].width = max(max_len + 4, 15)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="MyAgrinutrition_CRM_Field_Logs.xlsx"'
    wb.save(response)
    return response

# ==========================================
# 📊 DASHBOARDS & LIVE ANALYTICS PIPELINES
# ==========================================

def get_dashboard_context(request):
    """Central processing pipeline for managing filter logic on both templates."""
    sel_state = request.GET.get('state', '')
    sel_country = request.GET.get('country', '')
    sel_district = request.GET.get('district', '')
    sel_executive = request.GET.get('executive', '')
    sel_month = request.GET.get('month', '')
    sel_year = request.GET.get('year', '')

    farm_filters = Q()
    visit_filters = Q()
    product_filters = Q()

    if sel_state:
        farm_filters &= Q(state=sel_state)
        visit_filters &= Q(farm__state=sel_state)
        product_filters &= Q(visit__farm__state=sel_state)
    if sel_district:
        farm_filters &= Q(district=sel_district)
        visit_filters &= Q(farm__district=sel_district)
        product_filters &= Q(visit__farm__district=sel_district)
    if sel_executive:
        farm_filters &= Q(executive__username=sel_executive)
        visit_filters &= Q(executive__username=sel_executive)
        product_filters &= Q(visit__executive__username=sel_executive)
        
    if sel_month:
        visit_filters &= Q(visit_date__month=sel_month)
        product_filters &= Q(visit__visit_date__month=sel_month)
    if sel_year:
        visit_filters &= Q(visit_date__year=sel_year)
        product_filters &= Q(visit__visit_date__year=sel_year)

    total_rev = VisitedProductDetail.objects.filter(product_filters).aggregate(total=Sum('revenue_generated'))['total'] or 0
    vol_sold = VisitedProductDetail.objects.filter(product_filters).aggregate(total_qty=Sum('sale_quantity'))['total_qty'] or 0
    v_count = FarmVisitReport.objects.filter(visit_filters).count()
    
    hot_leads = VisitedProductDetail.objects.filter(product_filters, process_status='Hot').count()
    total_leads = VisitedProductDetail.objects.filter(product_filters).count()
    conv_rate = round((hot_leads / total_leads * 100), 1) if total_leads > 0 else 0.0

    district_data = Farm.objects.filter(farm_filters).values('district').annotate(count=Count('id')).order_by('-count')[:5]
    chart_labels = [d['district'] if d['district'] else 'Unknown' for d in district_data]
    chart_counts = [d['count'] for d in district_data]

    monthly_sales = (
        VisitedProductDetail.objects.filter(product_filters)
        .annotate(month=TruncMonth('visit__visit_date'))
        .values(
            'month', 
            'visit__executive__username', 
            'visit__farm__state', 
            'visit__farm__district', 
            'visit__farm__area'
        )
        .annotate(
            total_qty=Sum('sale_quantity'), 
            total_revenue=Sum('revenue_generated')
        )
        .order_by('-month', '-total_revenue')
    )

    return {
        'total_revenue': total_rev,
        'total_visits': v_count,
        'total_farms': Farm.objects.filter(farm_filters).count(),
        'total_sales_volume': vol_sold,
        'conversion_rate': conv_rate,
        'recent_visits': FarmVisitReport.objects.filter(visit_filters).select_related('farm').prefetch_related('products').order_by('-visit_date')[:10],
        'monthly_sales': monthly_sales,
        
        'state_list': Farm.objects.values_list('state', flat=True).distinct().exclude(state=''),
        'district_list': Farm.objects.values_list('district', flat=True).distinct().exclude(district=''),
        'executive_list': User.objects.filter(filed_visit_reports__isnull=False).values_list('username', flat=True).distinct(),
        'country_list': ['India'],
        
        'chart_labels_js': json.dumps(chart_labels if chart_labels else ["No Data Available"]),
        'chart_counts_js': json.dumps(chart_counts if chart_counts else [0]),
        
        'selected_state': sel_state,
        'selected_country': sel_country,
        'selected_district': sel_district,
        'selected_executive': sel_executive,
        'selected_month': sel_month,
        'selected_year': sel_year,
    }


@login_required(login_url='/crm/login/')
def dashboard_home(request):
    """Renders the Core KPI Summary Panel (Counters, Conversion, & Dispatches)"""
    context = get_dashboard_context(request)
    return render(request, 'crm_core/dashboard.html', context)


@login_required(login_url='/crm/login/')
def dashboard_analytics(request):
    """Renders the Advanced Analytics Telemetry Dashboard (Full Multi-Graphs Visualization)"""
    context = get_dashboard_context(request)
    return render(request, 'crm_core/analytics_report.html', context)


@login_required(login_url='/crm/login/')
def executive_analytics_view(request):
    """Fixed route configuration pointing to the correct analytics template configuration"""
    context = get_dashboard_context(request)
    return render(request, 'crm_core/analytics_report.html', context)


# ==========================================
# 🛰️ GEOLOCATION & DEPENDENT FILTER UTILITIES
# ==========================================

def get_location_details(request):
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    return JsonResponse({'status': 'success', 'state': 'Detected State', 'district': 'Detected District'})


def get_dependent_filters(request):
    """Dynamic cascade endpoint filtering districts by chosen state choice."""
    state_query = request.GET.get('state', '')
    if state_query:
        districts = list(Farm.objects.filter(state=state_query).values_list('district', flat=True).distinct().exclude(district=''))
        return JsonResponse({'districts': districts})
    return JsonResponse({'sub_segments': ['Layer', 'Broiler', 'Shrimp', 'Fish']})

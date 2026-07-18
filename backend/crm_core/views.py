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
            if district.lower() == 'namakkal':
                state = 'Tamil Nadu'
            else:
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

    # 📊 Expanded comprehensive headers to fully incorporate field observations and pipeline states
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

    all_products = VisitedProductDetail.objects.filter(export_filters).select_related(
        'visit__farm', 'visit__executive'
    ).order_by('-visit__visit_date')
    
    current_row = 2
    for p in all_products:
        v = p.visit
        f = v.farm if v else None
        
        # Core Parameters
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
        
        # 🟢 Added: Farm Problem & Poultry Shed Population Inventories
        ws_data.cell(row=current_row, column=11, value=v.farm_problem if v and v.farm_problem else "None reported")
        ws_data.cell(row=current_row, column=12, value=getattr(v, 'chicks_count', 0))
        ws_data.cell(row=current_row, column=13, value=getattr(v, 'grower_count', 0))
        ws_data.cell(row=current_row, column=14, value=getattr(v, 'layer_count', 0))
        ws_data.cell(row=current_row, column=15, value=getattr(v, 'culling_bird', 0))
        
        # Immediate Order Metrics
        ws_data.cell(row=current_row, column=16, value=p.product_name)
        ws_data.cell(row=current_row, column=17, value=p.sale_quantity)
        ws_data.cell(row=current_row, column=18, value=float(p.primary_price))
        ws_data.cell(row=current_row, column=14 + 5, value=float(p.revenue_generated)) # Column 19
        
        # 🟢 Added: Dynamic Pipeline Projections Matrix Data
        ws_data.cell(row=current_row, column=20, value=p.potential_quantity)
        ws_data.cell(row=current_row, column=21, value=p.target_quantity)
        ws_data.cell(row=current_row, column=22, value=p.unit_type)
        ws_data.cell(row=current_row, column=23, value=p.process_status)
        ws_data.cell(row=current_row, column=24, value=f"{p.conversion_percentage}%")
        
        # Live Geolocation Links
        gps_cell = ws_data.cell(row=current_row, column=25)
        if f and f.latitude and f.longitude:
            gps_cell.value = "View on Map"
            gps_cell.hyperlink = f"https://maps.google.com/?q={f.latitude},{f.longitude}"
            gps_cell.font = Font(name="Segoe UI", size=11, color="0000FF", underline="single")
        else:
            gps_cell.value = "No GPS Data"
            gps_cell.font = Font(name="Segoe UI", size=11, color="64748B", italic=True)

        # Style application pass across all 25 active layout boundaries
        for c_idx in range(1, 26):
            cell_item = ws_data.cell(row=current_row, column=c_idx)
            cell_item.border = thin_border
            if c_idx in [12, 13, 14, 15, 17, 20, 21, 24]:  # Align numerical tracking data sets centrally
                cell_item.alignment = Alignment(horizontal="center")
                
        current_row += 1

    # Format column layout adjustments safely
    for col in ws_data.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_data.column_dimensions[col_letter].width = max(max_len + 4, 14)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="MyAgrinutrition_CRM_Field_Logs.xlsx"'
    wb.save(response)
    return response

# ==========================================
# 📊 DASHBOARDS & LIVE ANALYTICS PIPELINES
# ==========================================

def get_dashboard_context(request):
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
        
        # 🟢 SECURED WORKSPACE FILTER: Hides admins and staff, only shows field executives.
        'executive_list': User.objects.filter(is_active=True, is_staff=False, is_superuser=False).values_list('username', flat=True).distinct(),
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


# ==========================================
# 🛰️ GEOLOCATION & DEPENDENT FILTER UTILITIES
# ==========================================

def get_location_details(request):
    """
    Processes incoming map telemetry coordinates dynamically.
    Uses a multi-tier API setup to guarantee live lookups anywhere in India.
    """
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        return JsonResponse({'status': 'error', 'message': 'Missing coordinates'}, status=400)
        
    # --- TIER 1: PRIMARY LOOKUP (OpenStreetMap Nominatim) ---
    try:
        headers = {
            'User-Agent': 'AgriNutritionCRM_Production_Engine/2.0 (operations@myagrinutrition.com)'
        }
        api_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        
        response = requests.get(api_url, headers=headers, timeout=4)
        if response.status_code == 200:
            data = response.json()
            address = data.get('address', {})
            
            district = address.get('district') or address.get('county') or address.get('subdistrict') or address.get('city_district') or address.get('state_district')
            area = address.get('suburb') or address.get('village') or address.get('town') or address.get('neighbourhood') or address.get('city') or address.get('road')
            state = address.get('state')
            
            if district and area and state:
                return JsonResponse({
                    'state': state.strip(),
                    'district': district.replace('District', '').strip(),
                    'area': area.strip()
                })
    except Exception:
        pass  # Fail gracefully over to Tier 2 if blocked or timed out

    # --- TIER 2: AUTOMATIC LIVE BACKUP (BigDataCloud Client API) ---
    try:
        backup_url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage=en"
        backup_response = requests.get(backup_url, timeout=4)
        
        if backup_response.status_code == 200:
            b_data = backup_response.json()
            
            state = b_data.get('principalSubdivision', 'Unknown State')
            area = b_data.get('locality', '').strip()
            
            # Deep scan the administrative lookup array to extract the local District name dynamically
            district = 'Unknown District'
            for admin_layer in b_data.get('informative', []):
                if admin_layer.get('order') == 4 or 'district' in admin_layer.get('description', '').lower():
                    district = admin_layer.get('name', district)
                    break
            
            if not area and b_data.get('lookupSource'):
                area = b_data.get('lookupSource')

            return JsonResponse({
                'state': state,
                'district': district.replace('District', '').strip(),
                'area': area if area else f"Zone ({lat[:7]}, {lon[:7]})"
            })
    except Exception:
        pass

    # --- TIER 3: EMERGENCY TELEMETRY STRIP (If completely offline/both APIs fail) ---
    # Instead of guessing text, it feeds the coordinate fingerprints back so the form can still submit.
    return JsonResponse({
        'state': 'Live GPS Active',
        'district': f"Dist: {lat[:7]}N",
        'area': f"Loc: {lon[:7]}E"
    })


def get_dependent_filters(request):
    state_query = request.GET.get('state', '')
    if state_query:
        districts = list(Farm.objects.filter(state=state_query).values_list('district', flat=True).distinct().exclude(district=''))
        return JsonResponse({'districts': districts})
    return JsonResponse({'sub_segments': ['Layer', 'Broiler', 'Shrimp', 'Fish']})

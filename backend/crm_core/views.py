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
                return redirect('dashboard_analytics')
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
                    return redirect('dashboard_analytics')
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
                        unit_type=p_unit,
                        primary_price=0.00,
                        revenue_generated=0.00,
                        process_status=status,
                        conversion_percentage=conv_pct
                    )

            messages.success(request, "Agri-Field visit logging record processed successfully!")
            if request.user.is_staff or request.user.is_superuser:
                return redirect('dashboard_analytics')
            
            return render(request, 'crm_core/farm_visit_form.html', {'saved_data': request.POST})

        except Exception as e:
            messages.error(request, f"Database transaction block failed: {str(e)}")
            return render(request, 'crm_core/farm_visit_form.html', {'saved_data': request.POST})

    return redirect('render_visit_form')


# ==========================================
# 📥 EXCEL REPORTING ENGINE EXPORT
# ==========================================

@login_required(login_url='/crm/login/')
def export_visits_to_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Field Visit Logs"
    ws.views.sheetView[0].showGridLines = True
    
    navy_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    font_header = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    font_body = Font(name="Segoe UI", size=10, color="000000")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'), right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'), bottom=Side(style='thin', color='CBD5E1')
    )
    
    headers = [
        "Visit ID", "Date", "Executive", "Farm Name", "Owner Name", 
        "Contact", "Sector", "District", "Area", "Problem Statement",
        "Product Tracked", "Sale Qty", "Unit", "Rate (Price)", 
        "Revenue Generated", "Pipeline Status", "Conv %"
    ]
    
    for col_num, header_title in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header_title
        cell.font = font_header
        cell.fill = navy_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    
    visit_details = VisitedProductDetail.objects.select_related(
        'visit', 'visit__farm', 'visit__executive'
    ).order_by('-visit__visited_at')
    
    row_index = 2
    for detail in visit_details:
        v_report = detail.visit
        farm = v_report.farm
        
        row_data = [
            v_report.id,
            v_report.visited_at.strftime('%Y-%m-%d %H:%M') if hasattr(v_report, 'visited_at') and v_report.visited_at else 'N/A',
            v_report.executive.get_full_name() if v_report.executive else 'System',
            farm.farm_name,
            farm.owner_name,
            farm.contact_number,
            f"{farm.business_type} ({farm.sub_segment})",
            farm.district,
            farm.area,
            v_report.farm_problem,
            detail.product_name,
            detail.sale_quantity,
            detail.unit_type,
            detail.primary_price,
            detail.revenue_generated,
            detail.process_status,
            f"{detail.conversion_percentage}%"
        ]
        
        for col_index, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_index, column=col_index)
            cell.value = value
            cell.font = font_body
            cell.border = thin_border
            if col_index in [1, 2, 6, 13, 16, 17]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_index in [12, 14, 15]:
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if col_index in [14, 15]:
                    cell.number_format = '"₹"#,##0.00'
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
        row_index += 1

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
    ws.row_dimensions[1].height = 28

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="AgriNutrition_Field_Visits.xlsx"'
    wb.save(response)
    return response


# ==========================================
# 📊 DASHBOARDS & LIVE ANALYTICS PIPELINES
# ==========================================

@login_required(login_url='/crm/login/')
def dashboard_home(request):
    """Renders the central platform navigation workspace."""
    return render(request, 'crm_core/dashboard_home.html')


@login_required(login_url='/crm/login/')
def dashboard_analytics(request):
    """Processes pipeline data metrics for managers."""
    context = {
        'total_revenue': VisitedProductDetail.objects.aggregate(total=Sum('revenue_generated'))['total'] or 0,
        'total_visits': FarmVisitReport.objects.count(),
        'active_farms': Farm.objects.count(),
    }
    return render(request, 'crm_core/dashboard_analytics.html', context)


@login_required(login_url='/crm/login/')
def executive_analytics_view(request):
    """Renders performance breakdowns for individual ground agents."""
    return render(request, 'crm_core/executive_analytics.html')


# ==========================================
# 🛰️ GEOLOCATION & DEPENDENT FILTER UTILITIES
# ==========================================

def get_location_details(request):
    """API endpoint to parse live tracking coordinates."""
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    return JsonResponse({'status': 'success', 'state': 'Detected State', 'district': 'Detected District'})


def get_dependent_filters(request):
    """API endpoint running background context lookups on dropdown fields."""
    return JsonResponse({'sub_segments': ['Layer', 'Broiler', 'Shrimp', 'Fish']})

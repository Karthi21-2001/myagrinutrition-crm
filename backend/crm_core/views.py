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
        
        state = request.POST.get('state', 'State')
        district = request.POST.get('district')
        area = request.POST.get('area')
        farm_problem = request.POST.get('farm_problem')
        
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
                        'state': state if state else 'State',
                        'district': district if district else '',
                        'area': area if area else '',
                        'latitude': latitude,
                        'longitude': longitude,
                    }
                )
                
                if not created and business_type:
                    farm_instance.business_type = business_type
                    if state:
                        farm_instance.state = state
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
            return redirect('render_visit_form')

        except Exception as e:
            messages.error(request, f"Database transaction block failed: {str(e)}")
            return redirect(request.META.get('HTTP_REFERER', 'render_visit_form'))

    return redirect('render_visit_form')


@login_required(login_url='/crm/login/')
def get_location_details(request):
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    if not lat or not lon:
        return JsonResponse({'error': 'Missing coordinates'}, status=400)
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
        headers = {'User-Agent': 'AgriCRM_Field_App/1.0'}
        response = requests.get(url, headers=headers).json()
        address_data = response.get('address', {})
        area = address_data.get('suburb') or address_data.get('village') or address_data.get('county') or "Unknown Area"
        district = address_data.get('state_district') or address_data.get('district') or address_data.get('city') or "Unknown District"
        state = address_data.get('state') or "Unknown State"
        return JsonResponse({'state': state, 'district': district, 'area': area})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ==========================================
# 📥 EXCEL EXPORT ENGINE (EXEMPTED FOR LIVE SYNC)
# ==========================================

@csrf_exempt
def export_visits_to_excel(request):
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
        'Visit Date', 'Executive Name', 'Farm Name', 'Owner Name', 'Contact Number', 'Sector Segment',
        'State', 'District', 'Area / Suburb', 'Product Name', 'Sale Qty', 'Price (INR)', 'Revenue Generated'
    ]

    for col_idx, text in enumerate(headers, 1):
        cell = ws_data.cell(row=1, column=col_idx, value=text)
        cell.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color=dark_slate, end_color=dark_slate, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws_data.row_dimensions[1].height = 28

    all_products = VisitedProductDetail.objects.all().select_related('visit__farm', 'visit__executive').order_by('-visit__visit_date')
    
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
        ws_data.cell(row=current_row, column=7, value=f.state if f else "")
        ws_data.cell(row=current_row, column=8, value=f.district if f else "")
        ws_data.cell(row=current_row, column=9, value=f.area if f else "")
        ws_data.cell(row=current_row, column=10, value=p.product_name)
        ws_data.cell(row=current_row, column=11, value=p.sale_quantity)
        ws_data.cell(row=current_row, column=12, value=float(p.primary_price))
        ws_data.cell(row=current_row, column=13, value=float(p.revenue_generated))
        
        for c_idx in range(1, 14):
            ws_data.cell(row=current_row, column=c_idx).border = thin_border
        current_row += 1

    for col in ws_data.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_data.column_dimensions[col_letter].width = max(max_len + 4, 15)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="AgriNutrition_Field_Logs_Data.xlsx"'
    wb.save(response)
    return response


# ==========================================
# 📊 LIVE DASHBOARD ANALYTICS ENGINES
# ==========================================

@login_required(login_url='/crm/login/')
def dashboard_home(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('render_visit_form')

    state = request.GET.get('state', '').strip()
    country = request.GET.get('country', '').strip()
    district = request.GET.get('district', '').strip()
    executive = request.GET.get('executive', '').strip()
    month = request.GET.get('month', '').strip()
    year = request.GET.get('year', '').strip()

    farm_filters = Q()
    visit_filters = Q()
    action_filters = Q()

    if country and country != 'All' and hasattr(Farm, 'country'):
        farm_filters &= Q(country__iexact=country)
        visit_filters &= Q(farm__country__iexact=country)
        action_filters &= Q(visit__farm__country__iexact=country)
    if state and state != 'All':
        farm_filters &= Q(state__iexact=state)
        visit_filters &= Q(farm__state__iexact=state)
        action_filters &= Q(visit__farm__state__iexact=state)
    if district and district != 'All':
        farm_filters &= Q(district__iexact=district)
        visit_filters &= Q(farm__district__iexact=district)
        action_filters &= Q(visit__farm__district__iexact=district)
    if executive and executive != 'All':
        visit_filters &= Q(executive__username__iexact=executive)
        action_filters &= Q(visit__executive__username__iexact=executive)
    if month and month != 'All':
        visit_filters &= Q(visit_date__month=month)
        action_filters &= Q(visit__visit_date__month=month)
    if year and year != 'All':
        farm_filters &= Q(visit_date__year=year)
        visit_filters &= Q(visit_date__year=year)
        action_filters &= Q(visit__visit_date__year=year)

    state_list = Farm.objects.exclude(state__isnull=True).values_list('state', flat=True).distinct().order_by('state')
    country_list = Farm.objects.exclude(country__isnull=True).values_list('country', flat=True).distinct().order_by('country') if hasattr(Farm, 'country') else []
    district_list = Farm.objects.exclude(district__isnull=True).values_list('district', flat=True).distinct().order_by('district')
    
    # 🎯 UPDATED: Exclude admin/staff accounts from dropdown options
    executive_list = User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True).values_list('username', flat=True).distinct().order_by('username')

    total_farms = Farm.objects.filter(farm_filters).count()
    total_visits = FarmVisitReport.objects.filter(visit_filters).count()
    
    sales_metrics = VisitedProductDetail.objects.filter(action_filters).aggregate(
        total_vol=Sum('sale_quantity'),
        total_rev=Sum(F('sale_quantity') * F('primary_price'), output_field=DecimalField())
    )
    total_sales_volume = sales_metrics['total_vol'] or 0
    total_revenue = sales_metrics['total_rev'] or 0.00

    visits_with_sales = FarmVisitReport.objects.filter(visit_filters).filter(products__sale_quantity__gt=0).distinct().count()
    conversion_rate = round((visits_with_sales / total_visits * 100), 1) if total_visits > 0 else 0.0

    recent_visits = FarmVisitReport.objects.filter(visit_filters).select_related('farm', 'executive').order_by('-visit_date')[:15]

    monthly_sales = VisitedProductDetail.objects.filter(action_filters).filter(sale_quantity__gt=0)\
        .annotate(month=TruncMonth('visit__visit_date'))\
        .values('month', 'visit__executive__username', 'visit__farm__state', 'visit__farm__district', 'visit__farm__area')\
        .annotate(
            total_qty=Sum('sale_quantity'), 
            total_revenue=Sum(F('sale_quantity') * F('primary_price'), output_field=DecimalField())
        )\
        .order_by('-month', 'visit__farm__district')

    chart_data = FarmVisitReport.objects.filter(visit_filters).values('farm__district').annotate(count=Count('id')).order_by('-count')[:8]
    chart_labels_js = [item['farm__district'] if item['farm__district'] else "Unknown" for item in chart_data]
    chart_counts_js = [item['count'] for item in chart_data]

    context = {
        'state_list': state_list,
        'country_list': country_list,
        'district_list': district_list,
        'executive_list': executive_list,
        
        'selected_state': state,
        'selected_country': country,
        'selected_district': district,
        'selected_executive': executive,
        'selected_month': month,
        'selected_year': year,

        'total_farms': total_farms,
        'total_visits': total_visits,
        'conversion_rate': conversion_rate,
        'total_sales_volume': total_sales_volume,
        'total_revenue': round(float(total_revenue), 2),
        
        'recent_visits': recent_visits,
        'monthly_sales': monthly_sales,
        
        'chart_labels_js': json.dumps(chart_labels_js),
        'chart_counts_js': json.dumps(chart_counts_js),
    }
    return render(request, 'crm_core/dashboard.html', context)


@login_required(login_url='/crm/login/')
def dashboard_analytics(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('render_visit_form')

    state_query = request.GET.get('state', '').strip()
    country_query = request.GET.get('country', '').strip()
    district_query = request.GET.get('district', '').strip()
    executive_query = request.GET.get('executive', '').strip()
    month_query = request.GET.get('month', '').strip()
    year_query = request.GET.get('year', '').strip()

    farms_queryset = Farm.objects.all()
    reports_queryset = FarmVisitReport.objects.all().select_related('farm', 'executive')
    products_queryset = VisitedProductDetail.objects.all().select_related('visit__farm', 'visit__executive')

    if state_query and state_query != 'All':
        farms_queryset = farms_queryset.filter(state__iexact=state_query)
        reports_queryset = reports_queryset.filter(farm__state__iexact=state_query)
        products_queryset = products_queryset.filter(visit__farm__state__iexact=state_query)
        
    if country_query and country_query != 'All' and hasattr(Farm, 'country'):
        farms_queryset = farms_queryset.filter(country__iexact=country_query)
        reports_queryset = reports_queryset.filter(farm__country__iexact=country_query)
        products_queryset = products_queryset.filter(visit__farm__country__iexact=country_query)

    if district_query and district_query != 'All':
        farms_queryset = farms_queryset.filter(district__iexact=district_query)
        reports_queryset = reports_queryset.filter(farm__district__iexact=district_query)
        products_queryset = products_queryset.filter(visit__farm__district__iexact=district_query)

    if executive_query and executive_query != 'All':
        reports_queryset = reports_queryset.filter(executive__username__iexact=executive_query)
        products_queryset = products_queryset.filter(visit__executive__username__iexact=executive_query)

    if month_query and month_query != 'All':
        reports_queryset = reports_queryset.filter(visit_date__month=month_query)
        products_queryset = products_queryset.filter(visit__visit_date__month=month_query)

    if year_query and year_query != 'All':
        farms_queryset = farms_queryset.filter(visit_date__year=year_query)
        reports_queryset = reports_queryset.filter(visit_date__year=year_query)
        products_queryset = products_queryset.filter(visit__visit_date__year=year_query)

    total_farms = farms_queryset.count()
    total_visits = reports_queryset.values('farm__contact_number').distinct().count()
    unique_districts = farms_queryset.values('district').distinct().count()
    
    metrics = products_queryset.aggregate(
        total_sales=Sum('sale_quantity'),
        calculated_revenue=Sum(F('sale_quantity') * F('primary_price'), output_field=DecimalField())
    )

    sales_volume = metrics['total_sales'] or 0
    revenue_value = metrics['calculated_revenue'] or 0.00
    
    converted_contacts = reports_queryset.filter(
        products__sale_quantity__gt=0
    ).values('farm__contact_number').distinct().count()
    
    conversion_rate = round((converted_contacts / total_visits * 100), 1) if total_visits > 0 else 0
    
    district_query_agg = (
        reports_queryset.values('farm__district')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    district_labels = [d['farm__district'] if d['farm__district'] else "Unknown Area" for d in district_query_agg]
    district_counts = [d['count'] for d in district_query_agg]

    recent_visits = reports_queryset.order_by('-visit_date')[:8]

    monthly_sales = (
        products_queryset.filter(sale_quantity__gt=0)
        .annotate(month=TruncMonth('visit__visit_date'))
        .values('month', 'visit__executive__username', 'visit__farm__state', 'visit__farm__district', 'visit__farm__area')
        .annotate(
            total_qty=Sum('sale_quantity'),
            total_revenue=Sum(F('sale_quantity') * F('primary_price'), output_field=DecimalField())
        )
        .order_by('-month', 'visit__executive__username')
    )

    state_list = Farm.objects.exclude(state__isnull=True).values_list('state', flat=True).distinct()
    country_list = Farm.objects.exclude(country__isnull=True).values_list('country', flat=True).distinct() if hasattr(Farm, 'country') else []
    district_list = Farm.objects.exclude(district__isnull=True).values_list('district', flat=True).distinct()
    
    # 🎯 UPDATED: Exclude admin/staff accounts from dropdown options
    executive_list = User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True).values_list('username', flat=True).distinct()

    context = {
        'total_farms': total_farms,
        'total_visits': total_visits,
        'unique_districts': unique_districts,
        'total_sales_volume': sales_volume,
        'total_revenue': round(float(revenue_value), 2),
        'conversion_rate': conversion_rate,
        'recent_visits': recent_visits,
        'monthly_sales': monthly_sales,
        
        'state_list': state_list,
        'country_list': country_list,
        'district_list': district_list,
        'executive_list': executive_list,
        
        'selected_state': state_query,
        'selected_country': country_query,
        'selected_district': district_query,
        'selected_executive': executive_query,
        'selected_month': month_query,
        'selected_year': year_query,
        
        'chart_labels_js': json.dumps(district_labels),
        'chart_counts_js': json.dumps(district_counts),
    }
    return render(request, 'crm_core/dashboard.html', context)


# ==========================================
# 📊 VISUAL PERFORMANCE REPORT
# ==========================================

@login_required(login_url='/crm/login/')
def executive_analytics_view(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('render_visit_form')

    state_f = request.GET.get('state', 'All').strip()
    country_f = request.GET.get('country', 'All').strip()
    district_f = request.GET.get('district', 'All').strip()
    exec_f = request.GET.get('executive', 'All').strip()
    month_f = request.GET.get('month', 'All').strip()
    year_f = request.GET.get('year', 'All').strip()

    reports_qs = FarmVisitReport.objects.all().select_related('farm', 'executive')
    products_qs = VisitedProductDetail.objects.all().select_related('visit__farm', 'visit__executive')

    if state_f != 'All' and state_f != '':
        reports_qs = reports_qs.filter(farm__state__iexact=state_f)
        products_qs = products_qs.filter(visit__farm__state__iexact=state_f)
        
    if country_f != 'All' and country_f != '' and hasattr(Farm, 'country'):
        reports_qs = reports_qs.filter(farm__country__iexact=country_f)
        products_qs = products_qs.filter(visit__farm__country__iexact=country_f)

    if district_f != 'All' and district_f != '':
        reports_qs = reports_qs.filter(farm__district__iexact=district_f)
        products_qs = products_qs.filter(visit__farm__district__iexact=district_f)

    if exec_f != 'All' and exec_f != '':
        reports_qs = reports_qs.filter(executive__username__iexact=exec_f)
        products_qs = products_qs.filter(visit__executive__username__iexact=exec_f)

    if month_f != 'All' and month_f != '':
        reports_qs = reports_qs.filter(visit_date__month=month_f)
        products_qs = products_qs.filter(visit__visit_date__month=month_f)

    if year_f != 'All' and year_f != '':
        reports_qs = reports_qs.filter(visit_date__year=year_f)
        products_qs = products_qs.filter(visit__visit_date__year=year_f)

    user_visits = reports_qs.values('executive__username').annotate(total_visits=Count('id')).order_by('-total_visits')
    user_labels = [item['executive__username'] or 'Unknown' for item in user_visits]
    user_counts = [item['total_visits'] for item in user_visits]

    zonal_sales = products_qs.filter(sale_quantity__gt=0).values('visit__farm__district').annotate(
        revenue=Sum(F('sale_quantity') * F('primary_price'), output_field=DecimalField())
    ).order_by('-revenue')
    zone_labels = [item['visit__farm__district'] if item['visit__farm__district'] else 'Unknown Area' for item in zonal_sales]
    zone_data = [float(item['revenue'] or 0) for item in zonal_sales]

    yearly_sales = products_qs.filter(sale_quantity__gt=0).annotate(year=TruncYear('visit__visit_date')).values('year').annotate(
        revenue=Sum(F('sale_quantity') * F('primary_price'), output_field=DecimalField())
    ).order_by('year')
    year_labels = [item['year'].strftime('%Y') if item['year'] else 'N/A' for item in yearly_sales]
    year_data = [float(item['revenue'] or 0) for item in yearly_sales]

    monthly_sales_qs = products_qs.filter(sale_quantity__gt=0).annotate(month=TruncMonth('visit__visit_date')).values('month').annotate(
        revenue=Sum(F('sale_quantity') * F('primary_price'), output_field=DecimalField())
    ).order_by('month')
    month_labels = [item['month'].strftime('%b %Y') if item['month'] else 'N/A' for item in monthly_sales_qs]
    month_data = [float(item['revenue'] or 0) for item in monthly_sales_qs]

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'labels': user_labels, 'values': user_counts,
            'zone_labels': zone_labels, 'zone_data': zone_data,
            'year_labels': year_labels, 'year_data': year_data,
            'month_labels': month_labels, 'month_data': month_data,
        })

    context = {
        'user_labels_js': json.dumps(user_labels), 'user_counts_js': json.dumps(user_counts),
        'zone_labels_js': json.dumps(zone_labels), 'zone_data_js': json.dumps(zone_data),
        'year_labels_js': json.dumps(year_labels), 'year_data_js': year_data,
        'month_labels_js': json.dumps(month_labels), 'month_data_js': month_data,
        'states': Farm.objects.exclude(state__isnull=True).values_list('state', flat=True).distinct().order_by('state'),
        'countries': Farm.objects.exclude(country__isnull=True).values_list('country', flat=True).distinct().order_by('country') if hasattr(Farm, 'country') else [],
        'districts': Farm.objects.exclude(district__isnull=True).values_list('district', flat=True).distinct().order_by('district'),
        
        # 🎯 UPDATED: Exclude admin/staff accounts from dropdown options
        'executives': User.objects.filter(is_active=True).exclude(is_staff=True).exclude(is_superuser=True).values_list('username', flat=True).distinct().order_by('username'),
    }
    return render(request, 'crm_core/analytics_report.html', context)


# ==========================================
# ⚙️ CASCADING FILTER UTILITY SERVICES
# ==========================================

@login_required(login_url='/crm/login/')
def get_dependent_filters(request):
    state = request.GET.get('state', 'All').strip()
    country = request.GET.get('country', 'All').strip()

    records = FarmVisitReport.objects.all().select_related('farm', 'executive')

    if country != 'All' and country != '' and hasattr(Farm, 'country'):
        records = records.filter(farm__country__iexact=country)
    if state != 'All' and state != '':
        records = records.filter(farm__state__iexact=state)

    available_districts = list(
        records.exclude(farm__district__isnull=True)
        .values_list('farm__district', flat=True)
        .distinct()
        .order_by('farm__district')
    )
    
    # 🎯 UPDATED: Exclude admin/staff entries implicitly by targeting only non-admin user values matched with logs
    available_executives = list(
        records.exclude(executive__isnull=True)
        .filter(executive__is_staff=False, executive__is_superuser=False)
        .values_list('executive__username', flat=True)
        .distinct()
        .order_by('executive__username')
    )

    return JsonResponse({
        'status': 'success',
        'districts': available_districts,
        'executives': available_executives
    })

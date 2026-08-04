# crm_core/utils/whatsapp_formatter.py

def build_farm_visit_message(visit_report):
    """
    visit_report: a FarmVisitReport instance, with .farm and .executive accessible.
    """
    farm = visit_report.farm
    executive = visit_report.executive
    executive_name = (
        executive.get_full_name() or executive.username
        if executive else "Unassigned"
    )

    template = (
        "🔔 New Farm Visit Update\n"
        "👤 Executive: {executive_name}\n"
        "🏡 Farm Name: {farm_name}\n"
        "📍 Location: {district} – {area}\n"
        "📅 Visit Date: {visit_date}\n"
        "📝 Visit Summary: {visit_summary}\n"
        "✅ Status: {visit_status}\n"
        "📌 Next Follow-up: {next_followup}\n\n"
        "Thank you,\n"
        "MyAgrinutrition CRM Team"
    )

    return template.format(
        executive_name=executive_name,
        farm_name=farm.farm_name,
        district=farm.district or "N/A",
        area=farm.area or "N/A",
        visit_date=visit_report.visit_date.strftime("%d-%b-%Y"),
        visit_summary=visit_report.farm_problem or "N/A",
        visit_status=visit_report.get_visit_status_display(),
        next_followup=(
            visit_report.next_visit_date.strftime("%d-%b-%Y")
            if visit_report.next_visit_date else "N/A"
        ),
    )
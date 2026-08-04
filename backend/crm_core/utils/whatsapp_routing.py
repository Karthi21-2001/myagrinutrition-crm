# crm_core/utils/whatsapp_routing.py

from crm_core.models import SalesExecutiveProfile


def get_target_group(visit_report):
    """
    visit_report: a FarmVisitReport instance.
    Returns the exact WhatsApp group title to send to.
    """
    executive = visit_report.executive
    if not executive:
        raise ValueError(f"Visit #{visit_report.id} has no executive assigned.")

    try:
        profile = executive.sales_profile
    except SalesExecutiveProfile.DoesNotExist:
        raise ValueError(
            f"User '{executive.username}' has no SalesExecutiveProfile "
            f"(missing employee_id/area/team/group setup)."
        )

    group = profile.whatsapp_group
    if not group or not group.is_active:
        raise ValueError(
            f"No active WhatsApp group configured for {profile.employee_id}."
        )

    return group.whatsapp_group_title
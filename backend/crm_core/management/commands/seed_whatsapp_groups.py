# crm/management/commands/seed_whatsapp_groups.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from crm_core.models import WhatsAppGroup, SalesExecutiveProfile

User = get_user_model()


GROUPS_DATA = [
    {
        "name": "TN Aqua - Sales",
        "whatsapp_group_title": "TN - Aqua- My Agri + Nxtage ( Sales)",  # confirm exact WhatsApp title
        "area": "TN",
        "team": "Sales",
        "executives": [
            ("MurugesanMYA070", "Murugesan"),
            ("SelvaMYA063", "Selva"),
        ],
    },
    {
        "name": "Namakkal - Sales Reporting",
        "whatsapp_group_title": "Nxtage- My Agri -Namakkal_( Sales reporting)",
        "area": "Namakkal",
        "team": "Sales Reporting",
        "executives": [
            ("KarthikMYA018", "Karthik"),
            ("SathishMYA074", "Sathish"),
        ],
    },
    {
        "name": "AP - Sales Report",
        "whatsapp_group_title": "My Agri+Nxtage AP (Sales report)",
        "area": "AP",
        "team": "Sales Report",
        "executives": [
            ("SaiMYA049", "Sai"),
        ],
    },
    {
        "name": "CBE - Sales Reporting",
        "whatsapp_group_title": "Nxtage+My Agri - CBE  (Sales Reporting)",
        "area": "CBE",
        "team": "Sales Reporting",
        "executives": [
            ("SubashMYA071", "Subash"),
        ],
    },
]


class Command(BaseCommand):
    help = "Seed WhatsApp groups and link sales executives via employee ID"

    def handle(self, *args, **kwargs):
        for group_data in GROUPS_DATA:
            group, created = WhatsAppGroup.objects.update_or_create(
                name=group_data["name"],
                defaults={
                    "whatsapp_group_title": group_data["whatsapp_group_title"],
                    "area": group_data["area"],
                    "team": group_data["team"],
                    "is_active": True,
                },
            )
            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} group: {group.name}")

            for emp_id, first_name in group_data["executives"]:
                # username derived from employee_id — adjust if you already
                # have a different username convention for existing Users
                user, user_created = User.objects.get_or_create(
                    username=emp_id,
                    defaults={"first_name": first_name},
                )
                if user_created:
                    self.stdout.write(f"  Created user: {user.username}")

                profile, profile_created = SalesExecutiveProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "employee_id": emp_id,
                        "area": group_data["area"],
                        "team": group_data["team"],
                        "whatsapp_group": group,
                    },
                )
                p_action = "Created" if profile_created else "Updated"
                self.stdout.write(f"  {p_action} profile: {profile}")

        self.stdout.write(self.style.SUCCESS("Seeding complete."))
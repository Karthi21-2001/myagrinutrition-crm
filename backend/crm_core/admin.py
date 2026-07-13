from django.contrib import admin
from django.apps import apps

# Automatically scan and display all underlying tables safely
app_models = apps.get_app_config('crm_core').get_models()

for model in app_models:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
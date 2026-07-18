from django.apps import AppConfig
import sys

class CrmCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crm_core'

    def ready(self):
        # 🚀 Safe startup execution once all apps are initialized
        # Prevents running migrations during local utilities like makemigrations
        if 'manage.py' not in sys.argv:
            from django.core.management import call_command
            try:
                print("App registry ready. Running production database migrations...")
                call_command('migrate', interactive=False)
                print("Database migrations successfully executed!")
            except Exception as e:
                print(f"Startup migration failed: {e}", file=sys.stderr)
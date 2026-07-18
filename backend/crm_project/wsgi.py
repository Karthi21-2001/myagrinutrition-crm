import os
import sys
from django.core.wsgi import get_wsgi_application
from django.core.management import call_command

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_project.settings')

# 🚀 FREE RENDER WORKAROUND: Force migrations on startup
try:
    print("Running database migrations via WSGI startup...")
    call_command('migrate', interactive=False)
    print("Database migrations applied successfully!")
except Exception as e:
    print(f"Migration fallback warning: {e}", file=sys.stderr)

# Get the WSGI application
application = get_wsgi_application()

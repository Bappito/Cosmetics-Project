"""WSGI file for PythonAnywhere.

Copy this whole file into the Web tab > "WSGI configuration file" (replace what is there).
Replace YOUR_USERNAME with your PythonAnywhere username. The secrets are read from
erp_secrets.env in your home folder, which is kept out of the repository.
"""
import os
import sys
from pathlib import Path

USERNAME = "YOUR_USERNAME"
PROJECT = Path(f"/home/{USERNAME}/Cosmetics-Project")
ENV_FILE = Path(f"/home/{USERNAME}/erp_secrets.env")

if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "erp_web.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()

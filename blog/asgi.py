# blog/asgi.py
"""
ASGI config for blog project.

It exposes the ASGI callable as a module-level variable named ``application``.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blog.settings')

application = get_asgi_application()
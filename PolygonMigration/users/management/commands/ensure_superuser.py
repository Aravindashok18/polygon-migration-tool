"""
Create the first staff superuser from environment variables, if it does not exist yet.

Used on hosts without shell access (e.g. Render free tier), where
`createsuperuser` cannot be run interactively. Safe to run on every start.

    DJANGO_SUPERUSER_EMAIL       required
    DJANGO_SUPERUSER_PASSWORD    required
    DJANGO_SUPERUSER_FIRST_NAME  optional (default "Admin")
    DJANGO_SUPERUSER_LAST_NAME   optional (default "User")
    DJANGO_SUPERUSER_USERNAME    optional (default: part of the email before @)
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a superuser from DJANGO_SUPERUSER_* environment variables if none exists for that email."

    def handle(self, *args, **options):
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")
        if not email or not password:
            self.stdout.write("ensure_superuser: DJANGO_SUPERUSER_EMAIL/PASSWORD not set, skipping.")
            return

        User = get_user_model()
        if User.objects.filter(email=email).exists():
            self.stdout.write(f"ensure_superuser: {email} already exists.")
            return

        User.objects.create_superuser(
            email=email,
            password=password,
            username=os.getenv("DJANGO_SUPERUSER_USERNAME") or email.split("@")[0],
            first_name=os.getenv("DJANGO_SUPERUSER_FIRST_NAME", "Admin"),
            last_name=os.getenv("DJANGO_SUPERUSER_LAST_NAME", "User"),
            contact_number=os.getenv("DJANGO_SUPERUSER_CONTACT_NUMBER", ""),
            college=os.getenv("DJANGO_SUPERUSER_COLLEGE", ""),
        )
        self.stdout.write(self.style.SUCCESS(f"ensure_superuser: created {email}."))

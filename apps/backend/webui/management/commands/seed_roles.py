from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


ROLE_NAMES = [
    "risk_admin",
    "risk_owner",
    "risk_reviewer",
]


class Command(BaseCommand):
    help = "Create default RiskFabric role groups."

    def handle(self, *args, **options):
        for role_name in ROLE_NAMES:
            _, created = Group.objects.get_or_create(name=role_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group: {role_name}"))
            else:
                self.stdout.write(f"Group already exists: {role_name}")

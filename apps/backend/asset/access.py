from django.db.models import Q

from core.permissions import ROLE_RISK_ADMIN, has_any_role

from .models import Asset


def can_view_all_assets(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or has_any_role(user, ROLE_RISK_ADMIN)


def accessible_assets(user):
    if not user or not user.is_authenticated:
        return Asset.objects.none()
    if can_view_all_assets(user):
        return Asset.objects.all()
    return (
        Asset.objects.filter(
            Q(access_users=user)
            | Q(access_teams__members=user)
            | (Q(access_users__isnull=True) & Q(access_teams__isnull=True))
        )
        .distinct()
    )

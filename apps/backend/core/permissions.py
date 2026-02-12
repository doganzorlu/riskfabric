from rest_framework.permissions import SAFE_METHODS, BasePermission


ROLE_RISK_ADMIN = "risk_admin"
ROLE_RISK_OWNER = "risk_owner"
ROLE_RISK_REVIEWER = "risk_reviewer"
ROLE_GOVERNANCE_MANAGER = "governance_manager"
ROLE_COMPLIANCE_AUDITOR = "compliance_auditor"


def has_any_role(user, *role_names: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=role_names).exists()


class IsRiskManagerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return has_any_role(request.user, ROLE_RISK_ADMIN, ROLE_RISK_OWNER)


class IsRiskReviewerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return has_any_role(request.user, ROLE_RISK_ADMIN, ROLE_RISK_REVIEWER)


class IsRiskAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return has_any_role(request.user, ROLE_RISK_ADMIN)


class IsGovernanceManagerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return has_any_role(request.user, ROLE_RISK_ADMIN, ROLE_GOVERNANCE_MANAGER)


class IsComplianceAuditorOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return has_any_role(request.user, ROLE_RISK_ADMIN, ROLE_COMPLIANCE_AUDITOR)


class CanRunSync(BasePermission):
    def has_permission(self, request, view):
        return has_any_role(request.user, ROLE_RISK_ADMIN)

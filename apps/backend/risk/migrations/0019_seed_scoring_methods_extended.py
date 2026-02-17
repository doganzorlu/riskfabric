from django.db import migrations


def seed_scoring_methods(apps, schema_editor):
    RiskScoringMethod = apps.get_model("risk", "RiskScoringMethod")

    methods = [
        {
            "code": "CIA_V1",
            "name": "CIA (Confidentiality/Integrity/Availability)",
            "method_type": "cia",
            "likelihood_weight": 1.0,
            "impact_weight": 1.0,
            "treatment_effectiveness_weight": 1.0,
            "is_active": True,
            "is_default": False,
        },
        {
            "code": "CVSS_V3",
            "name": "CVSS v3",
            "method_type": "cvss",
            "likelihood_weight": 1.0,
            "impact_weight": 1.0,
            "treatment_effectiveness_weight": 1.0,
            "is_active": True,
            "is_default": False,
        },
        {
            "code": "DREAD_V1",
            "name": "DREAD",
            "method_type": "dread",
            "likelihood_weight": 1.0,
            "impact_weight": 1.0,
            "treatment_effectiveness_weight": 1.0,
            "is_active": True,
            "is_default": False,
        },
        {
            "code": "CLASSIC_V1",
            "name": "Classic",
            "method_type": "classic",
            "likelihood_weight": 1.0,
            "impact_weight": 1.0,
            "treatment_effectiveness_weight": 1.0,
            "is_active": True,
            "is_default": False,
        },
        {
            "code": "OWASP_V1",
            "name": "OWASP",
            "method_type": "owasp",
            "likelihood_weight": 1.0,
            "impact_weight": 1.0,
            "treatment_effectiveness_weight": 1.0,
            "is_active": True,
            "is_default": False,
        },
    ]

    existing_default = RiskScoringMethod.objects.filter(is_active=True, is_default=True).exists()

    for item in methods:
        RiskScoringMethod.objects.update_or_create(code=item["code"], defaults=item)

    if not existing_default:
        RiskScoringMethod.objects.filter(code="CIA_V1").update(is_default=True)


def unseed_scoring_methods(apps, schema_editor):
    RiskScoringMethod = apps.get_model("risk", "RiskScoringMethod")
    RiskScoringMethod.objects.filter(code__in=["CIA_V1", "CVSS_V3", "DREAD_V1", "CLASSIC_V1", "OWASP_V1"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0018_criticalservice_hazard_risk_dynamic_risk_score_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_scoring_methods, unseed_scoring_methods),
    ]

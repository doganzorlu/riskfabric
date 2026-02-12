from django.db import migrations


def seed_scoring_methods(apps, schema_editor):
    RiskScoringMethod = apps.get_model("risk", "RiskScoringMethod")

    methods = [
        {
            "code": "INHERENT_V1",
            "name": "Inherent Baseline",
            "method_type": "inherent",
            "likelihood_weight": 1.0,
            "impact_weight": 1.0,
            "treatment_effectiveness_weight": 1.0,
            "is_default": True,
            "is_active": True,
        },
        {
            "code": "RESIDUAL_V1",
            "name": "Residual Weighted",
            "method_type": "residual",
            "likelihood_weight": 1.0,
            "impact_weight": 1.0,
            "treatment_effectiveness_weight": 1.2,
            "is_default": False,
            "is_active": True,
        },
        {
            "code": "CUSTOM_WEIGHTED_V1",
            "name": "Custom Weighted",
            "method_type": "custom",
            "likelihood_weight": 1.3,
            "impact_weight": 1.1,
            "treatment_effectiveness_weight": 1.0,
            "is_default": False,
            "is_active": True,
        },
    ]

    for item in methods:
        RiskScoringMethod.objects.update_or_create(code=item["code"], defaults=item)


def unseed_scoring_methods(apps, schema_editor):
    RiskScoringMethod = apps.get_model("risk", "RiskScoringMethod")
    RiskScoringMethod.objects.filter(code__in=["INHERENT_V1", "RESIDUAL_V1", "CUSTOM_WEIGHTED_V1"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0004_riskscoringmethod_alter_risk_impact_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_scoring_methods, unseed_scoring_methods),
    ]

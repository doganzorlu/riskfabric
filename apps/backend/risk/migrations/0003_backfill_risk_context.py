from django.db import migrations


def backfill_risk_context(apps, schema_editor):
    Risk = apps.get_model("risk", "Risk")

    for risk in Risk.objects.select_related("primary_asset", "primary_asset__business_unit", "primary_asset__cost_center", "primary_asset__section", "primary_asset__asset_type").all():
        asset = risk.primary_asset
        if not asset:
            continue

        risk.business_unit_id = asset.business_unit_id
        risk.cost_center_id = asset.cost_center_id
        risk.section_id = asset.section_id
        risk.asset_type_id = asset.asset_type_id
        risk.save(update_fields=["business_unit", "cost_center", "section", "asset_type"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0002_risk_asset_type_risk_business_unit_risk_cost_center_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_risk_context, noop_reverse),
    ]

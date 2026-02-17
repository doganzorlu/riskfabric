from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0022_risk_scoring_parameter_models"),
    ]

    operations = [
        migrations.AlterField(
            model_name="servicebiaprofile",
            name="service",
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="bia_profile", to="risk.criticalservice", verbose_name="Service"),
        ),
        migrations.AlterField(
            model_name="servicebiaprofile",
            name="mao_hours",
            field=models.PositiveIntegerField(default=24, verbose_name="MAO/MTPD (h)"),
        ),
        migrations.AlterField(
            model_name="servicebiaprofile",
            name="rto_hours",
            field=models.PositiveIntegerField(default=8, verbose_name="RTO (h)"),
        ),
        migrations.AlterField(
            model_name="servicebiaprofile",
            name="rpo_hours",
            field=models.PositiveIntegerField(default=4, verbose_name="RPO (h)"),
        ),
        migrations.AlterField(
            model_name="servicebiaprofile",
            name="notes",
            field=models.TextField(blank=True, verbose_name="Notes"),
        ),
    ]

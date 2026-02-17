from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0020_risk_cia_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="riskscoringmethod",
            name="method_type",
            field=models.CharField(
                choices=[
                    ("inherent", "Inherent"),
                    ("residual", "Residual"),
                    ("custom", "Custom"),
                    ("cvss", "CVSS"),
                    ("dread", "DREAD"),
                    ("classic", "Classic"),
                    ("owasp", "OWASP"),
                    ("cia", "CIA"),
                ],
                default="custom",
                max_length=32,
            ),
        ),
    ]

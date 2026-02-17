from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0019_seed_scoring_methods_extended"),
    ]

    operations = [
        migrations.AddField(
            model_name="risk",
            name="confidentiality",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
                verbose_name="Confidentiality",
            ),
        ),
        migrations.AddField(
            model_name="risk",
            name="integrity",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
                verbose_name="Integrity",
            ),
        ),
        migrations.AddField(
            model_name="risk",
            name="availability",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
                verbose_name="Availability",
            ),
        ),
    ]

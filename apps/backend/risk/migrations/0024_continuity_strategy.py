from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0023_alter_servicebiaprofile_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContinuityStrategy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=255)),
                (
                    "strategy_type",
                    models.CharField(
                        choices=[
                            ("redundancy", "Redundancy"),
                            ("backup", "Backup"),
                            ("manual", "Manual"),
                            ("vendor", "Vendor"),
                            ("workaround", "Workaround"),
                        ],
                        default="backup",
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("active", "Active"), ("retired", "Retired")],
                        default="draft",
                        max_length=32,
                    ),
                ),
                (
                    "readiness_level",
                    models.CharField(
                        choices=[
                            ("planned", "Planned"),
                            ("in_progress", "In Progress"),
                            ("ready", "Ready"),
                            ("tested", "Tested"),
                        ],
                        default="planned",
                        max_length=32,
                    ),
                ),
                ("rto_target_hours", models.PositiveIntegerField(default=8)),
                ("rpo_target_hours", models.PositiveIntegerField(default=4)),
                ("owner", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "bia_profile",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="continuity_strategies", to="risk.servicebiaprofile"),
                ),
                (
                    "scenario",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="continuity_strategies", to="risk.scenario"),
                ),
                (
                    "service",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="continuity_strategies", to="risk.criticalservice"),
                ),
            ],
            options={
                "ordering": ["code"],
            },
        ),
    ]

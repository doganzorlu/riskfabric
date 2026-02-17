import json
from typing import Any, Dict

from django.core.management.base import BaseCommand, CommandError

from risk.models import Scenario
from risk.services.resilience import simulate_scenario


class Command(BaseCommand):
    help = "Simulate a scenario impact using hazard links and BIA escalation curves."

    def add_arguments(self, parser):
        parser.add_argument("scenario_id", type=int)
        parser.add_argument("--duration-hours", type=int, default=None)
        parser.add_argument("--format", choices=["text", "json"], default="text")

    def handle(self, *args, **options):
        scenario_id = options["scenario_id"]
        duration_hours = options.get("duration_hours")
        output_format = options["format"]

        try:
            scenario = Scenario.objects.select_related("hazard").get(id=scenario_id)
        except Scenario.DoesNotExist as exc:
            raise CommandError(f"Scenario not found: {scenario_id}") from exc

        result = simulate_scenario(scenario, duration_hours=duration_hours)

        if output_format == "json":
            payload: Dict[str, Any] = {
                "scenario": str(result["scenario"]),
                "hazard": str(result["hazard"]),
                "duration_hours": result["duration_hours"],
                "failed_asset_ids": result["failed_asset_ids"],
                "services": [
                    {
                        "service": str(service["service"]),
                        "impact": service["impact"],
                        "failed_asset_ids": service["failed_asset_ids"],
                    }
                    for service in result["services"]
                ],
            }
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        self.stdout.write(
            f"Scenario: {result['scenario']} (Hazard: {result['hazard']}) - Duration: {result['duration_hours']}h"
        )
        self.stdout.write(f"Failed assets: {len(result['failed_asset_ids'])}")

        if not result["services"]:
            self.stdout.write("No impacted services found.")
            return

        for service_entry in result["services"]:
            service = service_entry["service"]
            impact = service_entry["impact"]
            self.stdout.write(f"- {service} | Failed assets: {len(service_entry['failed_asset_ids'])}")
            if not impact:
                self.stdout.write("  Impact: No BIA profile")
                continue
            for category, detail in impact.items():
                self.stdout.write(f"  {category}: {detail['label']} (L{detail['level']})")

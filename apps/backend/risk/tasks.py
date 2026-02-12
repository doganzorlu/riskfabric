from __future__ import annotations

from datetime import datetime

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.audit import create_audit_event

from .models import RiskNotification, RiskReportRun, RiskReportSchedule


def _schedule_due(schedule: RiskReportSchedule, now: datetime) -> bool:
    if not schedule.is_active:
        return False
    if schedule.last_run_at and schedule.last_run_at.date() == now.date():
        return False
    if schedule.frequency == RiskReportSchedule.FREQUENCY_DAILY:
        return now.hour == schedule.hour and now.minute >= schedule.minute
    if schedule.frequency == RiskReportSchedule.FREQUENCY_WEEKLY:
        if schedule.day_of_week is None:
            return False
        return now.weekday() == schedule.day_of_week and now.hour == schedule.hour and now.minute >= schedule.minute
    if schedule.frequency == RiskReportSchedule.FREQUENCY_MONTHLY:
        if schedule.day_of_month is None:
            return False
        return now.day == schedule.day_of_month and now.hour == schedule.hour and now.minute >= schedule.minute
    return False


@shared_task
def send_scheduled_reports():
    now = timezone.now()
    schedules = RiskReportSchedule.objects.filter(is_active=True)
    for schedule in schedules:
        if not _schedule_due(schedule, now):
            continue

        RiskReportRun.objects.create(schedule=schedule, status="success", message="Scheduled report executed.")
        schedule.last_run_at = now
        schedule.save(update_fields=["last_run_at", "updated_at"])

        recipients = [item.strip() for item in (schedule.recipients or "").split(",") if item.strip()]
        if recipients:
            user_model = get_user_model()
            users = user_model.objects.filter(username__in=recipients)
        else:
            user_model = get_user_model()
            users = user_model.objects.filter(groups__name="risk_admin").distinct()

        for user in users:
            RiskNotification.objects.create(
                user=user,
                risk=None,
                notification_type=RiskNotification.TYPE_REPORT_READY,
                message=f"Report '{schedule.name}' ({schedule.report_type}) is ready.",
            )

        create_audit_event(
            action="report.schedule.run",
            entity_type="risk_report_schedule",
            entity_id=schedule.id,
            metadata={"report_type": schedule.report_type, "frequency": schedule.frequency},
            request=None,
        )

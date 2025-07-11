from celery import shared_task
import logging

log = logging.getLogger(__name__)


@shared_task
def update_stl_redis():
    from statistical.models import MonthSales, DayStatistical, CityStatistical
    MonthSales.task_add_order_sum()
    DayStatistical.task_add_order_sum()
    CityStatistical.task_add_order_sum()


@shared_task
def update_stl_total_redis():
    from statistical.models import TotalStatistical
    TotalStatistical.task_change_data()


@shared_task
def task_add_session_agent_day_sum():
    from statistical.models import SessionAgentDaySum
    SessionAgentDaySum.task_add_session_agent_day_sum()


@shared_task
def task_add_session_cps_day_sum():
    from statistical.models import SessionCpsDaySum
    SessionCpsDaySum.task_add_session_cps_day_sum()

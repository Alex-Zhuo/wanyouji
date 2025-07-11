from celery import shared_task
import logging

log = logging.getLogger(__name__)


@shared_task
def task_add_discount_total():
    from mall.models import TheaterCardUserRecord
    return TheaterCardUserRecord.task_add_discount_total()


from celery import shared_task
import logging

log = logging.getLogger(__name__)


@shared_task
def session_push_to_ks():
    from kuaishou_wxa.models import KsGoodsConfig
    return KsGoodsConfig.session_push_to_ks()


@shared_task
def settle_order_to_ks():
    # 自动结算不需要推结算
    from kuaishou_wxa.models import KsOrderSettleRecord
    return KsOrderSettleRecord.settle_order()


@shared_task
def ks_order_report_task():
    from kuaishou_wxa.models import KsOrderReportRecord
    KsOrderReportRecord.ks_order_report_task()


@shared_task
def ks_check_cps():
    from kuaishou_wxa.models import KsOrderSettleRecord
    KsOrderSettleRecord.ks_check_cps()

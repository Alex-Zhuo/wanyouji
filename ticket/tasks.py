from celery import shared_task
import logging

log = logging.getLogger(__name__)


@shared_task
def auto_sync_mai_zuo():
    from ticket.models import SessionInfo
    return SessionInfo.auto_sync_mai_zuo()


@shared_task
def auto_mai_zuo_login():
    from ticket.models import MaiZuoTask
    return MaiZuoTask.login_task()


@shared_task
def auto_init_mai_zuo():
    from ticket.models import MaiZuoTask
    MaiZuoTask.pull_record()


# @shared_task
# def down_load_task():
#     from ticket.models import DownLoadTask
#     DownLoadTask.do_task()


@shared_task
def add_session_actual_amount():
    from ticket.models import SessionInfo
    SessionInfo.task_add_actual_amount()


@shared_task
def send_show_start_notice():
    from ticket.models import TicketOrder
    TicketOrder.send_show_start_notice()


@shared_task
def update_ticket_file_stock_from_redis():
    from ticket.models import TicketFile
    TicketFile.update_stock_from_redis()


@shared_task
def send_show_start_notice_give():
    from ticket.models import TicketGiveRecord
    TicketGiveRecord.send_show_start_notice_give()


@shared_task
def settle_order_award_task():
    from ticket.models import TicketOrder
    TicketOrder.send_award_task()


@shared_task
def check_add_booking_task():
    # 补抖音预约单
    from ticket.models import TicketOrder
    TicketOrder.check_add_booking()


@shared_task
def ticket_order_expire():
    from ticket.models import TicketOrder
    TicketOrder.check_auto_expire()


@shared_task
def goods_push_to_dou_yin():
    from ticket.models import SessionPushTiktokTask
    SessionPushTiktokTask.push_to_dou_yin()


@shared_task
def goods_draft_dou_yin():
    from ticket.models import SessionInfo
    SessionInfo.goods_draft_dou_yin()


@shared_task
def auth_check_over_time_code():
    from ticket.models import TicketOrder
    TicketOrder.auth_check_over_time_code()


@shared_task
def auth_check_over_time_code_tiktok():
    from ticket.models import TicketOrder
    TicketOrder.auth_check_over_time_code_tiktok()


@shared_task
def plan_to_dou_yin():
    from ticket.models import CommonPlanCps, LiveRoomCps, ShortVideoCps
    CommonPlanCps.common_plan_to_dou_yin()
    LiveRoomCps.live_room_plan_to_dou_yin()
    ShortVideoCps.short_video_plan_to_dou_yin()


@shared_task
def update_goods_sales():
    from ticket.models import TicketFile
    TicketFile.update_goods_sales()


@shared_task
def update_focus_num():
    from ticket.models import ShowPerformer
    ShowPerformer.update_focus_num()


@shared_task
def check_cps_source():
    from ticket.models import TicketOrder
    TicketOrder.check_cps_source_new()


@shared_task
def show_expire_off():
    from ticket.models import ShowProject
    ShowProject.auto_expire_off()


@shared_task
def pull_tiktok_qual():
    from ticket.models import TikTokQualRecord
    TikTokQualRecord.pull_tiktok_qual()


@shared_task
def task_add_commission_balance():
    from shopping_points.models import UserAccount
    UserAccount.task_add_commission_balance()

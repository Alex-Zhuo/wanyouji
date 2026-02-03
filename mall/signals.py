# coding: utf-8
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
import logging
from mall.models import User, TheaterCardUserDetail
from django.dispatch import Signal

from renovation.models import SubPages

logger = logging.getLogger(__name__)
receipt_paid_signal = Signal(providing_args=['instance'])
new_user_signal = Signal(providing_args=['request', 'query_params'])
user_status_signal = Signal()


# 改成不维护不生成path了
# @receiver(post_save, sender=User)
# def user_saved(sender, **kwargs):
#     """
#     检查并设置用户的path
#     :param sender:
#     :param kwargs:
#     :return:
#     """
#     created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
#     logger.debug('user_saved: handled {}, {}'.format(sender, kwargs))
#
#     def update_user_without_generate_signal(do_update):
#         try:
#             post_save.disconnect(user_saved, User)
#             do_update()
#         finally:
#             post_save.connect(user_saved, User)
#
#     if created:
#         # 本次更新，不产生信号
#         update_user_without_generate_signal(instance.get_or_update_path)
#         # query_set = Coupon.objects.filter(to_new_user=True)
#         # map(lambda x: x.send_to_user(instance, 1), query_set)
#     else:
#         if update_fields and 'parent' in update_fields:
#             logger.debug('parent')
#             # admin site里更新字段会触发这里，这里要更新自己
#             # User.set_parent里的update_fields= ['parent_id',..]不会触发这里
#             update_user_without_generate_signal(instance.refresh_my_tree)
#             # instance.account.refresh_parent(instance.parent)
#         else:
#             update_user_without_generate_signal(instance.update_iv)


@receiver(user_logged_in, sender=User)
def set_request_logged_in(sender, **kwargs):
    request = kwargs.get('request')
    request.after_login = True
    if request.user.is_staff and not request.user.own_session_key or request.user.own_session_key != request.session.session_key:
        request.user.own_session_key = request.session.session_key
        request.user.save(update_fields=['own_session_key'])


@receiver(user_logged_out, sender=User)
def set_request_logged_out(sender, **kwargs):
    request = kwargs.get('request')
    request.after_logout = True


@receiver(post_save, sender=SubPages)
def set_page_code(sender, **kwargs):
    created, instance = map(kwargs.get, ('created', 'instance'))
    if created:
        instance.set_page_code()


@receiver(post_delete, sender=User)
def user_delete(sender, **kwargs):
    instance = kwargs.get('instance')
    from mall.user_cache import share_code_user_cache_delete
    share_code_user_cache_delete(instance.share_code)


@receiver(post_save, sender=TheaterCardUserDetail)
def tc_card_create(sender, **kwargs):
    instance = kwargs.get('instance')
    instance.set_user_id()

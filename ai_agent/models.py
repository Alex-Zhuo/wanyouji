# coding=utf-8
from django.db import models
from django.conf import settings


class DefaultQuestions(models.Model):
    title = models.CharField('问题内容', max_length=500)
    is_use = models.BooleanField('是否使用', default=True)
    display_order = models.PositiveSmallIntegerField('排序', default=0, help_text='从小到大排列')
    create_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = '默认问题'
        ordering = ['display_order']


class HistoryChat(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.CASCADE)
    update_at = models.DateTimeField('最新提问时间', null=True)

    class Meta:
        verbose_name_plural = verbose_name = '对话历史记录'

    def __str__(self):
        return self.user.get_full_name()

    @classmethod
    def get_inst(cls, user):
        inst, _ = cls.objects.get_or_create(user=user)
        return inst


class HistoryChatDetail(models.Model):
    hc = models.ForeignKey(HistoryChat, verbose_name='对话历史记录', on_delete=models.CASCADE)
    question = models.TextField('提问', max_length=2000)
    answer = models.TextField('回答')
    create_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = '对话历史明细'
        ordering = ['-pk']

    def __str__(self):
        return self.create_at.strftime('%Y-%m-%d %H:%M')

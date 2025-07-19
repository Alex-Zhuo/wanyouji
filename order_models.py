from django.db import models
from django.core.validators import MinValueValidator
import re


class IdInfo(models.Model):
    """证件信息模型"""
    
    # 证件类型选择
    ID_TYPE_CHOICES = [
        (1, '身份证'),
        (2, '护照'),
        (4, '军人证'),
        (8, '台湾居民来往内地通行证'),
        (16, '港澳居民来往内地大陆通行证'),
    ]
    
    number = models.CharField(max_length=50, help_text="证件号")
    name = models.CharField(max_length=100, help_text="证件姓名")
    type = models.IntegerField(choices=ID_TYPE_CHOICES, help_text="证件类型")
    
    class Meta:
        db_table = 'id_info'
        verbose_name = '证件信息'
        verbose_name_plural = '证件信息'
    
    def __str__(self):
        return f"{self.name} - {self.get_type_display()}"


class Entrance(models.Model):
    """入场口信息模型"""
    entrance_id = models.CharField(max_length=50, primary_key=True, help_text="入场口id")
    entrance_name = models.CharField(max_length=100, blank=True, null=True, help_text="入场口名称")
    
    class Meta:
        db_table = 'entrance'
        verbose_name = '入场口信息'
        verbose_name_plural = '入场口信息'
    
    def __str__(self):
        return self.entrance_name or self.entrance_id


class Ticket(models.Model):
    """票信息模型"""
    
    # 场次类型选择
    SESSION_TYPE_CHOICES = [
        (0, '普通场次'),
        (1, '联票场次'),
    ]
    
    # 兑换模式选择
    EXCHANGE_MODE_CHOICES = [
        (0, '联票码'),
        (1, '基础场次票码'),
    ]
    
    # 二维码类型选择
    QR_CODE_TYPE_CHOICES = [
        (1, '文本码'),
        (3, 'URL链接'),
    ]
    
    # 码状态选择
    STATE_CHOICES = [
        (0, '已生效'),
        (1, '已锁定'),
        (2, '已退'),
        (3, '转出中'),
        (4, '已转出'),
        (6, '转出票已退票'),
    ]
    
    # 核销状态选择
    CHECK_STATE_CHOICES = [
        (0, '未核销'),
        (1, '已核销'),
        (2, '部分核销'),
    ]
    
    # 基础字段
    id = models.CharField(max_length=50, primary_key=True, help_text="票ID")
    group_instance_id = models.CharField(max_length=50, blank=True, null=True, help_text="组合ID，套票时才有")
    event_id = models.CharField(max_length=50, help_text="节目id")
    event_name = models.CharField(max_length=200, help_text="节目名称")
    session_id = models.CharField(max_length=50, help_text="场次id")
    session_name = models.CharField(max_length=200, help_text="场次名称")
    
    # 场次相关
    session_type = models.IntegerField(
        choices=SESSION_TYPE_CHOICES,
        default=0,
        help_text="场次类型,0:普通场次;1:联票场次"
    )
    ticket_photo = models.URLField(blank=True, null=True, help_text="联票下单上传照片url")
    exchange_mode = models.IntegerField(
        choices=EXCHANGE_MODE_CHOICES,
        blank=True,
        null=True,
        help_text="兑换模式，0:联票码，1:基础场次票码"
    )
    
    # 票价信息
    ticket_type_id = models.CharField(max_length=50, help_text="票价id")
    ticket_type_name = models.CharField(max_length=100, help_text="票价名称")
    
    # 时间信息
    session_start_time = models.CharField(max_length=20, help_text="场次开始时间，格式：yyyy-MM-dd HH:mm")
    session_end_time = models.CharField(max_length=20, help_text="场次结束时间，格式：yyyy-MM-dd HH:mm")
    
    # 座位信息
    seat_id = models.CharField(max_length=50, blank=True, null=True, help_text="座位id")
    floor_name = models.CharField(max_length=100, blank=True, null=True, help_text="楼层名称")
    zone_name = models.CharField(max_length=100, blank=True, null=True, help_text="区域名称")
    seat_name = models.CharField(max_length=100, blank=True, null=True, help_text="座位名称")
    
    # 二维码信息
    check_in_code = models.TextField(blank=True, null=True, help_text="二维码")
    check_in_type = models.IntegerField(
        choices=QR_CODE_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text="二维码类型，1：文本码 3：URL链接"
    )
    
    # 状态信息
    state = models.IntegerField(
        choices=STATE_CHOICES,
        default=0,
        help_text="码状态,0：已生效；1：已锁定；2：已退；3：转出中；4：已转出；6：转出票已退票"
    )
    check_state = models.IntegerField(
        choices=CHECK_STATE_CHOICES,
        default=0,
        help_text="码状态,0：未核销；1：已核销；2：部分核销"
    )
    
    # 其他信息
    stock_code_id = models.CharField(max_length=50, blank=True, null=True, help_text="出票单ID")
    ticket_no = models.CharField(max_length=50, blank=True, null=True, help_text="票号")
    
    # 关联字段
    entrance_list = models.ManyToManyField(Entrance, blank=True, help_text="入场口信息")
    id_info = models.ForeignKey(
        IdInfo,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="票实名信息，一票一证时有值"
    )
    
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")
    updated_at = models.DateTimeField(auto_now=True, help_text="更新时间")
    
    class Meta:
        db_table = 'ticket'
        verbose_name = '票信息'
        verbose_name_plural = '票信息'
        indexes = [
            models.Index(fields=['event_id']),
            models.Index(fields=['session_id']),
            models.Index(fields=['ticket_type_id']),
            models.Index(fields=['group_instance_id']),
        ]
    
    def __str__(self):
        return f"{self.event_name} - {self.ticket_type_name}"
    
    @property
    def is_package_ticket(self):
        """是否为套票"""
        return self.group_instance_id is not None
    
    @property
    def is_union_session(self):
        """是否为联票场次"""
        return self.session_type == 1
    
    @property
    def is_checked_in(self):
        """是否已核销"""
        return self.check_state == 1
    
    @property
    def is_refunded(self):
        """是否已退票"""
        return self.state == 2
    
    def get_seat_info(self):
        """获取座位信息"""
        if self.seat_name:
            return f"{self.floor_name or ''} {self.zone_name or ''} {self.seat_name}"
        return "无座位信息"


class Order(models.Model):
    """订单模型"""
    
    # 订单状态选择
    ORDER_STATE_CHOICES = [
        (1, '已下单'),
        (2, '已支付'),
        (3, '已出票'),
        (5, '已完成'),
        (7, '已关闭'),
        (8, '已取消'),
    ]
    
    # 二维码类型选择
    QR_CODE_TYPE_CHOICES = [
        (1, '文本码'),
        (3, 'URL链接'),
    ]
    
    # 码状态选择
    CODE_STATE_CHOICES = [
        (0, '待生效'),
        (1, '已生效'),
        (2, '已核销'),
        (3, '已完成'),
        (4, '已失效'),
        (5, '已过期'),
        (6, '已退'),
    ]
    
    # 基础字段
    order_no = models.CharField(max_length=50, primary_key=True, help_text="彩艺云订单号")
    buyer_cellphone = models.CharField(max_length=20, help_text="购票人手机号")
    buyer_email = models.CharField(max_length=100, help_text="购票人邮箱")
    external_order_no = models.CharField(max_length=50, help_text="外部订单号")
    
    # 时间信息
    create_time = models.CharField(max_length=20, help_text="订单创建时间，格式：yyyy-MM-dd HH:mm:ss")
    auto_cancel_order_time = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="订单未支付自动取消时间，格式：yyyy-MM-dd HH:mm"
    )
    
    # 状态信息
    order_state = models.CharField(max_length=10, choices=ORDER_STATE_CHOICES, help_text="订单状态")
    
    # 换票信息
    exchange_code = models.CharField(max_length=100, help_text="换票码")
    exchange_qr_code = models.TextField(help_text="换二维票码")
    code_type = models.IntegerField(choices=QR_CODE_TYPE_CHOICES, help_text="二维码类型")
    code_state = models.CharField(max_length=10, choices=CODE_STATE_CHOICES, help_text="码状态")
    
    # 快递信息
    express_no = models.CharField(max_length=50, blank=True, null=True, help_text="快递单号")
    express_name = models.CharField(max_length=100, blank=True, null=True, help_text="快递公司名称")
    
    # 关联字段
    id_info = models.ForeignKey(
        IdInfo,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="单实名信息，一单一证时有值"
    )
    ticket_list = models.ManyToManyField(Ticket, blank=True, help_text="票信息")
    
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")
    updated_at = models.DateTimeField(auto_now=True, help_text="更新时间")
    
    class Meta:
        db_table = 'order'
        verbose_name = '订单'
        verbose_name_plural = '订单'
        indexes = [
            models.Index(fields=['buyer_cellphone']),
            models.Index(fields=['external_order_no']),
            models.Index(fields=['order_state']),
            models.Index(fields=['create_time']),
        ]
    
    def __str__(self):
        return f"{self.order_no} - {self.get_order_state_display()}"
    
    @property
    def is_paid(self):
        """是否已支付"""
        return self.order_state == '2'
    
    @property
    def is_completed(self):
        """是否已完成"""
        return self.order_state == '5'
    
    @property
    def is_cancelled(self):
        """是否已取消"""
        return self.order_state == '8'
    
    @property
    def has_express(self):
        """是否有快递信息"""
        return bool(self.express_no and self.express_name)
    
    @property
    def has_id_info(self):
        """是否有实名信息"""
        return self.id_info is not None
    
    def get_ticket_count(self):
        """获取票数量"""
        return self.ticket_list.count()
    
    def get_package_tickets(self):
        """获取套票"""
        return self.ticket_list.filter(group_instance_id__isnull=False)
    
    def get_basic_tickets(self):
        """获取基础票"""
        return self.ticket_list.filter(group_instance_id__isnull=True)
    
    def get_checked_in_tickets(self):
        """获取已核销的票"""
        return self.ticket_list.filter(check_state=1)
    
    def get_refunded_tickets(self):
        """获取已退票的票"""
        return self.ticket_list.filter(state=2)


# 便捷函数
def create_order_with_tickets(order_data, tickets_data):
    """创建订单和票信息"""
    # 创建订单
    order = Order.objects.create(**order_data)
    
    # 创建票信息
    for ticket_data in tickets_data:
        # 处理入场口信息
        entrance_list = ticket_data.pop('entrance_list', [])
        
        # 处理实名信息
        id_info_data = ticket_data.pop('id_info', None)
        id_info = None
        if id_info_data:
            id_info = IdInfo.objects.create(**id_info_data)
        
        # 创建票
        ticket = Ticket.objects.create(**ticket_data, id_info=id_info)
        
        # 添加入场口
        for entrance_data in entrance_list:
            entrance, _ = Entrance.objects.get_or_create(**entrance_data)
            ticket.entrance_list.add(entrance)
        
        # 添加到订单
        order.ticket_list.add(ticket)
    
    return order


def get_orders_by_state(state):
    """按状态获取订单"""
    return Order.objects.filter(order_state=state)


def get_orders_by_buyer(cellphone):
    """按购票人手机号获取订单"""
    return Order.objects.filter(buyer_cellphone=cellphone)


def get_orders_by_event(event_id):
    """按节目ID获取订单"""
    return Order.objects.filter(ticket_list__event_id=event_id).distinct()


def update_order_state(order_no, new_state):
    """更新订单状态"""
    order = Order.objects.get(order_no=order_no)
    order.order_state = new_state
    order.save()
    return order


def get_tickets_by_session(session_id):
    """按场次ID获取票"""
    return Ticket.objects.filter(session_id=session_id)


def get_available_tickets(event_id):
    """获取可用的票（未核销且未退票）"""
    return Ticket.objects.filter(
        event_id=event_id,
        state__in=[0, 1],  # 已生效或已锁定
        check_state__in=[0, 2]  # 未核销或部分核销
    ) 
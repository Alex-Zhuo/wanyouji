# coding:utf-8
from rest_framework.response import Response
from coupon.models import Coupon, UserCouponRecord, CouponBasic, CouponActivity
from coupon.serializers import CouponSerializer, UserCouponRecordSerializer, UserCouponRecordCreateSerializer, \
    UserCouponRecordAvailableNewSerializer, CouponActivitySerializer, UserCouponRecordActCreateSerializer
from home.views import ReturnNoDetailViewSet
from restframework_ext.filterbackends import OwnerFilterMixinDjangoFilterBackend
from restframework_ext.pagination import StandardResultsSetPagination
from restframework_ext.permissions import IsPermittedUser
from rest_framework.decorators import action
from restframework_ext.exceptions import CustomAPIException


class CouponViewSet(ReturnNoDetailViewSet):
    """
    消费卷列表
    """
    queryset = Coupon.objects.filter(status=Coupon.STATUS_ON)
    permission_classes = [IsPermittedUser]
    serializer_class = CouponSerializer
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get']

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def receive(self, request):
        """
        领取消费卷
        """
        s = UserCouponRecordCreateSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        s.create(s.validated_data)
        return Response()

    @action(methods=['get'], detail=False)
    def activity(self, request):
        """
        消费卷活动详情
        """
        act_no = request.GET.get('act_no')
        if not act_no:
            raise CustomAPIException('活动不存在')
        try:
            c_act = CouponActivity.objects.get(no=act_no, status=CouponActivity.ST_ON)
        except CouponActivity.DoesNotExist:
            raise CustomAPIException('活动已结束')
        data = CouponActivitySerializer(c_act, context={'request': request}).data
        return Response(data)

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def act_receive(self, request):
        """
        活动领取批量消费卷,一件领取
        """
        s = UserCouponRecordActCreateSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        ret = s.create(s.validated_data)
        msg = '领取成功！'
        if not ret:
            msg = '已抢光！'
        return Response(dict(msg=msg))


class UserCouponRecordViewSet(ReturnNoDetailViewSet):
    """
    用戶消費卷记录
    """
    queryset = UserCouponRecord.objects.all()
    serializer_class = UserCouponRecordSerializer
    permission_classes = [IsPermittedUser]
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    http_method_names = ['get', 'post']
    filter_fields = ['status']

    @action(methods=['post'], detail=False)
    def get_available_new(self, request):
        """
        查看可使用消費卷
        """
        s = UserCouponRecordAvailableNewSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        res = s.create(s.validated_data)
        return Response(self.serializer_class(res, many=True, context={'request': request}).data)

    @action(methods=['get'], detail=False)
    def pop_up(self, request):
        """
        用户是否弹窗
        """
        has_coupon = Coupon.objects.filter(status=Coupon.STATUS_ON).exists()
        data = dict(need_pop=False, img=None)
        if has_coupon:
            has = Coupon.get_pop_up(request.user.id)
            need_pop = False if has else True
            if not has:
                bc = CouponBasic.get()
                if bc:
                    data['img'] = request.build_absolute_uri(bc.image.url)
                else:
                    need_pop = False
            data['need_pop'] = need_pop
        return Response(data)

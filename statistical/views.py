from django.views.decorators.cache import cache_page
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import viewsets, views

# Create your views here.
from home.views import ReturnNoDetailViewSet
from restframework_ext.permissions import IsSuperUser, IsStaffUser
from statistical.models import TotalStatistical, SessionAgentDaySum, export_record, SessionCpsDaySum, export_cps_record
from statistical.serializers import TotalStatisticalSerializer, SessionSearchListSerializer
from restframework_ext.exceptions import CustomAPIException
from django.db.models import Q, Sum


class TotalStatisticalViewSet(ReturnNoDetailViewSet):
    queryset = TotalStatistical.objects.all()
    serializer_class = TotalStatisticalSerializer
    permission_classes = [IsSuperUser]
    http_method_names = ['get', 'post']

    def list(self, request, *args, **kwargs):
        inst = self.queryset.first()
        data = self.serializer_class(inst, context={'request': request}).data
        return Response(data)

    @action(methods=['get'], detail=False, permission_classes=[IsStaffUser])
    def get_session_list(self, request):
        kw = request.GET.get('kw')
        from ticket.models import SessionInfo
        if not kw:
            raise CustomAPIException('参数错误')
        qs = SessionInfo.objects.filter(is_delete=False, show__title__contains=kw)
        data = SessionSearchListSerializer(qs, many=True).data
        return Response(data)

    @action(methods=['post'], detail=False, permission_classes=[IsStaffUser])
    def session_agent_record(self, request):
        kw = request.data.get('kw')
        session_id = request.data.get('session_id')
        start_at = request.data.get('start_at')
        end_at = request.data.get('end_at')
        is_down = request.data.get('is_down')
        if not (kw and start_at and end_at and session_id):
            raise CustomAPIException('参数错误')
        qs = SessionAgentDaySum.objects.filter(session_id=int(session_id), create_at__gte=start_at,
                                               create_at__lte=end_at)
        if qs:
            qs = qs.filter(Q(agent__mobile=kw) | Q(agent__last_name=kw))
        if qs:
            data = qs.values('source_type').order_by('source_type').annotate(total_amount=Sum('amount'),
                                                                             commission_amount=Sum('c_amount'))
            inst = qs.first()
            if data:
                data = list(data)
                choices = dict(SessionAgentDaySum.ST_CHOICES)
                for dd in data:
                    dd['title'] = inst.session.show.title
                    dd['start_at'] = inst.session.start_at.strftime("%Y年%m月%d日 %H:%M")
                    dd['agent'] = str(inst.agent)
                    dd['date_at'] = '{}--{}'.format(start_at, end_at)
                    dd['source_type'] = choices[int(dd['source_type'])]
            if is_down:
                resp = export_record(data)
                return resp
            return Response(data)
        return Response()

    @action(methods=['get'], detail=False, permission_classes=[IsStaffUser])
    def get_platform_list(self, request):
        from ticket.models import TiktokUser
        data = dict(TiktokUser.ST_CHOICES)
        return Response(data)

    @action(methods=['post'], detail=False, permission_classes=[IsStaffUser])
    def session_cps_record(self, request):
        kw = request.data.get('kw')
        session_id = request.data.get('session_id')
        start_at = request.data.get('start_at')
        platform = request.data.get('platform')
        end_at = request.data.get('end_at')
        is_down = request.data.get('is_down')
        if not (kw and start_at and end_at and session_id and platform):
            raise CustomAPIException('参数错误')
        qs = SessionCpsDaySum.objects.filter(session_id=int(session_id), create_at__gte=start_at,
                                             create_at__lte=end_at, platform=int(platform))
        if qs:
            qs = qs.filter(Q(tiktok_nickname=kw) | Q(tiktok_douyinid=kw))
        if qs:
            data = qs.values('source_type').order_by('source_type').annotate(total_amount=Sum('amount'),
                                                                             commission_amount=Sum('c_amount'))
            inst = qs.first()
            if data:
                data = list(data)
                choices = dict(SessionCpsDaySum.ST_CHOICES)
                for dd in data:
                    dd['title'] = inst.session.show.title
                    dd['start_at'] = inst.session.start_at.strftime("%Y年%m月%d日 %H:%M")
                    dd['platform'] = inst.get_platform_display()
                    dd['agent'] = inst.tiktok_nickname
                    dd['date_at'] = '{}--{}'.format(start_at, end_at)
                    dd['source_type'] = choices[int(dd['source_type'])]
            if is_down:
                resp = export_cps_record(data)
                return resp
            return Response(data)
        return Response()

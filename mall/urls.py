# coding: utf-8

from mall.views import MembershipCardViewSet, MemberCardRecordViewSet, AgreementRecordViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

router.register(r'member_card', MembershipCardViewSet)
router.register(r'card_record', MemberCardRecordViewSet)
router.register(r'agree', AgreementRecordViewSet)

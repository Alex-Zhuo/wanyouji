# coding: utf-8

from mall.views import MembershipCardViewSet, MemberCardRecordViewSet, \
    AgreementRecordViewSet, TheaterCardViewSet, TheaterCardOrderViewSet, TheaterCardUserRecordViewSet, \
    TheaterCardChangeRecordViewSet, TheaterCardUserDetailViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

router.register(r'member_card', MembershipCardViewSet)
router.register(r'card_record', MemberCardRecordViewSet)
router.register(r'theater_card', TheaterCardViewSet)
router.register(r'theater_order', TheaterCardOrderViewSet)
router.register(r'my_theater_card', TheaterCardUserRecordViewSet)
router.register(r'my_tc_list', TheaterCardUserDetailViewSet)
router.register(r'theater_record', TheaterCardChangeRecordViewSet)
router.register(r'agree', AgreementRecordViewSet)

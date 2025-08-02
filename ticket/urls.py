# coding: utf-8
from rest_framework.routers import DefaultRouter

from ticket.views import VenuesViewSet, TicketColorViewSet, ShowCollectRecordViewSet, ShowProjectViewSet, \
    SessionSeatViewSet, SessionInfoViewSet, TicketFileViewSet, TicketOrderViewSet, ShowPerformerViewSet, \
    ShowUserViewSet, PerformerFocusRecordViewSet, ShowCommentImageViewSet, ShowCommentViewSet, TicketBookingViewSet, \
    TicketGiveRecordViewSet

router = DefaultRouter()

router.register('venues', VenuesViewSet)
router.register('shows', ShowProjectViewSet)
router.register('sessions', SessionInfoViewSet)
router.register('level', TicketFileViewSet)
router.register('color', TicketColorViewSet)
router.register('seats', SessionSeatViewSet, basename='seats')
router.register('collect', ShowCollectRecordViewSet)
router.register('order', TicketOrderViewSet)
# router.register('performer', ShowPerformerViewSet)
router.register('users', ShowUserViewSet)
router.register('focus', PerformerFocusRecordViewSet)
router.register('comment_img', ShowCommentImageViewSet)
router.register('comment', ShowCommentViewSet)
# router.register('booking', TicketBookingViewSet)
router.register('give', TicketGiveRecordViewSet)
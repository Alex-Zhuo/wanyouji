from rest_framework import routers
from shopping_points.views import UserAccountLevelViewSet, CommissionWithdrawViewSet, UserAccountViewSet, \
    UserCommissionChangeRecordViewSet, UserCommissionMonthRecordViewSet, ReceiptAccountViewSet

router = routers.DefaultRouter()

router.register('account_level', UserAccountLevelViewSet)
router.register('withdrawcom', CommissionWithdrawViewSet)
router.register('account', UserAccountViewSet)
router.register('commission', UserCommissionChangeRecordViewSet)
router.register('monthcom', UserCommissionMonthRecordViewSet)
router.register('receipt_account', ReceiptAccountViewSet)

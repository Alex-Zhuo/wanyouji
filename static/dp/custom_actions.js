/**
 * Created by jacky on 17/7/24.
 */
function scan_custom_actions() {
    django.jQuery.ajax({
        type: 'get',
        url: '/cv/dp/scan_custom_actions',
        success: function(data) {
            window.location.reload();
        }
    });
}

function check_receive() {
    django.jQuery.ajax({
        type: 'get',
        url: '/api/orders/refresh_receive/',
        success: function(data) {
            window.location.reload();
        }
    });
}

function pay_share_award() {
    django.jQuery.ajax({
        type: 'get',
        url: '/api/share/pay_all_of_approved/',
        success: function(data) {
            window.location.reload();
        }
    });
}
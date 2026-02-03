/**
 * Created by jacky on 17/9/23.
 */
function refresh_tree() {
    django.jQuery.ajax({
        type: 'get',
        url: '/api/users/refresh_tree/',
        success: function(data) {
            window.location.reload();
        }
    });
}
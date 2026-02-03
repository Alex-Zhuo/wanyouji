function generate() {
    django.jQuery.ajax({
        type: 'post',
        url: '/api/shopping_points/bonus/generate/',
        complete: function(jqXHR, textStatus) {
            console.log('status: ' + textStatus);
            window.location.reload();
        }
    });
}
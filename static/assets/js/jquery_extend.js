/**
 * Created by Administrator on 2017/11/29.
 */
django.jQuery.fn.serializeObject = function()
{
    var o = {};
    var a = this.serializeArray();
    django.jQuery.each(a, function() {
        if (o[this.name] !== undefined) {
            if (!o[this.name].push) {
                o[this.name] = [o[this.name]];
            }
            o[this.name].push(this.value || '');
        } else {
            o[this.name] = this.value || '';
        }
    });
    return o;
};
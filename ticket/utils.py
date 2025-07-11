# coding: utf-8
import os


def down_excel_dir():
    from django.conf import settings
    rel_url = settings.MEDIA_URL + '/'.join(['down', 'excel'])
    return os.path.join(settings.MEDIA_ROOT, 'down', 'excel'), rel_url, '/'.join(['down', 'excel'])


def excel_dir():
    dir, rel_url, xlsx_dir = down_excel_dir()
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return dir, rel_url, xlsx_dir


def _write_row_by_xlwt(ws, cells, row_index):
    """
    :param ws:
    :param cells: cell values
    :param row_index: 1-relative row index
    :return:
    """
    for col, cell in enumerate(cells, 0):
        ws.write(row_index - 1, col, cell)


# 根据经纬度计算出距离排序
def get_locations_queryset(queryset, lng: float, lat: float, max_distance: int = 0,is_show_type=False):
    """
    queryset: 查询集
    latitude: 纬度
    longitude: 精度
    max_distance:最大距离
    """

    gcd_formula = "6371 * acos(least(greatest(\
    cos(radians(%s)) * cos(radians(lat)) \
    * cos(radians(lng) - radians(%s)) + \
    sin(radians(%s)) * sin(radians(lat)) \
    , -1), 1))"

    from django.db.models.expressions import RawSQL
    sql = RawSQL(gcd_formula, (lat, lng, lat))
    if is_show_type:
        qs = queryset.annotate(distance=sql).order_by('distance')
    else:
        qs = queryset.annotate(distance=sql).order_by('distance')
    if max_distance:
        qs = qs.filter(distance__lt=max_distance)
    return qs


def qrcode_dir_order_codes_o():
    """
    二维码存放的文件目录、相对url(相对于media_root，不包含文件名)
    :return:
    """
    from django.conf import settings
    rel_url = settings.MEDIA_URL + '/'.join(['ticket', 'order_codes'])
    return os.path.join(settings.MEDIA_ROOT, 'ticket', 'order_codes'), rel_url


def qrcode_dir_order_codes():
    """
    在qrcode_dir创建目录
    :return:
    """
    dir, rel_url = qrcode_dir_order_codes_o()
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return dir, rel_url
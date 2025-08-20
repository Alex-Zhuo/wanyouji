# coding: utf-8
import os
from urllib.request import urlopen
import datetime
import qrcode
from PIL import Image, ImageFont, ImageDraw

try:
    from django.conf import settings

    assert settings.BASE_DIR
except Exception:
    from dj import settings
from PIL import Image, ImageOps


def get_current_week():
    # monday, sunday = datetime.date.today(), datetime.date.today()
    monday = datetime.date.today()
    one_day = datetime.timedelta(days=1)
    while monday.weekday() != 0:
        monday -= one_day
    # while sunday.weekday() != 6:
    #    sunday += one_day
    return monday


def _resolve_icon_box(size, default_size=120):
    w, h = size
    left, upper = (w - default_size) / 2, (h - default_size) / 2
    right, lower = left + default_size, upper + default_size
    return left, upper, right, lower


def _correct(icon, icon_box):
    width, height = icon_box[2] - icon_box[0], icon_box[3] - icon_box[1]
    if icon.size != (width, height):
        return icon.resize((width, height), Image.ANTIALIAS)
    return icon


def merge(bg, icon, icon_box):
    # transparent_bg = Image.new('RGBA', bg.size, (255,) * 4)
    bg, icon = bg.convert('RGBA'), icon.convert('RGBA')
    bg.paste(icon, icon_box, icon)
    # transparent_bg.paste(bg, (0, 0))
    # transparent_bg.paste(icon, icon_box, mask=icon)
    return bg


def generate(url, size, save_path=None, icon=None, icon_box=None):
    """
    generate qrcode for url. if icon given, then paste it to qrcode, if icon_position not given, will paste to
    center.
    :param save_path: the save path to save image file
    :param url: the url str
    :param size: 2-tuple in pixel for (width, height)
    :param icon: the icon source, which is a file path
    :param icon_box: a 4-tuple (left, top, right, lower), if not given will be set center, and set width, heigh to 50, 50
    :return:
        True: succeed
        False: failed
    """
    if size[0] < 330:
        version = 1
    else:
        version = (size[0] - 330) / 40 + 1
    qr = qrcode.QRCode(version=version, error_correction=qrcode.ERROR_CORRECT_H, border=0)
    qr.add_data(url)
    qr.make()
    img = qr.make_image()
    if img.size[0] > size[0]:
        img.thumbnail(size)
    elif img.size[0] < size[0]:
        img = img.resize(size)

    if icon:
        icon_img = Image.open(icon)
        icon_box = icon_box or _resolve_icon_box(img.size)
        icon_img = _correct(icon_img, icon_box)
        img = merge(img, icon_img, icon_box)
    if not save_path:
        return img
    else:
        img.save(save_path)
        img.close()


def merge_image(bg_img, icon, position):
    """

    :param bg_img:
    :param icon:
    :param position: 起点坐标2元组
    :return:
    """
    x, y = bg_img.size
    icon_box = position + (position[0] + icon.size[0], position[1] + icon.size[1])
    assert x >= icon_box[2] and y >= icon_box[3], ValueError('超出边界背景图边界')
    return merge(bg_img, icon, icon_box)


def gen_wxa_invite_code(wxa_code, save_path, nickname, avatar_url, sequence, bg_file=None):
    """
    生成小程序分享码
    :param save_path:
    :param wxa_code: wxa_code_file
    :return:
    """
    bg_file = os.path.join(settings.BASE_DIR, bg_file or 'mall/images/qng_wxa_bg.jpg')
    # img = merge_image(bg, Image.open(wxa_code))
    child = Image.open(wxa_code)
    child.thumbnail((220, 220))
    from mp.models import ShareQrcodeBackground
    qr_bg = ShareQrcodeBackground.objects.filter(enable=True).first()
    bg_path = 'mall/images/share_cds_v3.jpg' if not qr_bg else qr_bg.image.path
    bg = Image.open(bg_file or os.path.join(settings.BASE_DIR,
                                            bg_path)).convert('RGBA')
    res = merge_image(bg, child, (490, 1030))
    if avatar_url:
        avatar = open_image_by_url(avatar_url)
    else:
        default_avatar = os.path.join('mall/images/share_avatar_defult.png')
        avatar = Image.open(default_avatar)
    avatar = avatar.resize((120, 120))
    try:
        avatar = circle_thumbnail(avatar)
    except ValueError as e:
        if str(e) == "illegal image mode":
            # 图片有问题
            pass
    else:
        res = merge(res, avatar, (314, 726))

    draw = ImageDraw.Draw(res)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 30)
    width, _ = bg.size
    # 绿色: (00, 0xc6, 00), 黑色: 0, 0, 0
    if nickname:
        draw_text_align(draw, nickname, width, 5, (0, 0, 0), font, 920)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 30)
    font2 = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 40)

    draw_text_align_complex(draw,
                            [(u'我是第', font, (89, 89, 89), 0), (str(sequence), font2, (0xe6, 0, 0x39), 0),
                             (u'位分享者', font, (89, 89, 89), 0)], width, 5, 870)
    # draw_text_align(draw, u'我是第3123812位推荐者', width, 5, (59, 57, 57), font, 1400)
    if save_path:
        # res = res.resize(res.size, Image.ANTIALIAS)
        # res = res.convert('RGB')
        res.save(save_path)
        # res.save(save_path, optimize=True, quality=95)
    else:
        return res


def gen_wxa_invite_code_new(wxa_code, save_path, bg_file=None):
    """
    生成小程序分享码
    :param save_path:
    :param wxa_code: wxa_code_file
    :return:
    """
    bg_file = os.path.join(settings.BASE_DIR, bg_file or 'mall/images/qng_wxa_bg.jpg')
    # img = merge_image(bg, Image.open(wxa_code))
    child = Image.open(wxa_code)
    child.thumbnail((220, 220))
    from mp.models import ShareQrcodeBackground
    qr_bg = ShareQrcodeBackground.objects.filter(enable=True).first()
    bg_path = 'mall/images/share_cds_v3.jpg' if not qr_bg else qr_bg.image.path
    bg = Image.open(bg_file or os.path.join(settings.BASE_DIR,
                                            bg_path)).convert('RGBA')
    res = merge_image(bg, child, (490, 1030))
    if save_path:
        res.save(save_path)
    else:
        return res


def generate_wc_qrcode(url, text, avatar_url, save_path=None, bg_file=None):
    """
    use the jpg format to save is the smallest
    :param avatar_url:
    :param text: should be a str
    :param url:
    :param save_path:
    :param bg_file:
    :return:
    """
    child = generate(url, (234, 234))
    import os
    from dj import settings
    bg = Image.open(bg_file or os.path.join(settings.BASE_DIR,
                                            'mall/images/share_bg.jpg'))
    res = merge_image(bg, child, (70, 846))
    if avatar_url:
        avatar = open_image_by_url(avatar_url)
        avatar.thumbnail((60, 60))
        res = merge(res, avatar, (50, 50))
    draw = ImageDraw.Draw(res)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR,
                                           'mall/images/simsun.ttc'), 30)
    if text:
        draw.text((210, 46), text.decode('utf-8') if isinstance(text, str) else text, (234, 106, 5), font=font)
    draw.text((231, 82), u'立云在线', (234, 106, 5), font=font)
    if save_path:
        # res = res.resize(res.size, Image.ANTIALIAS)
        # res = res.convert('RGB')
        res.save(save_path)
        # res.save(save_path, optimize=True, quality=95)
    else:
        return res


def get_bg(bg_file=None):
    return Image.open(bg_file or os.path.join(settings.BASE_DIR,
                                              'mall/images/share_bg_v2.jpg'))


def generate_qrcode_ywyn(url, save_path=None, bg_file=None):
    child = generate(url, (226, 226))
    bg = get_bg(bg_file)
    res = merge_image(bg, child, (38, 896))
    if save_path:
        # res = res.resize(res.size, Image.ANTIALIAS)
        # res = res.convert('RGB')
        res.save(save_path)
        # res.save(save_path, optimize=True, quality=95)
    else:
        return res


def open_image_by_url(url):
    return Image.open(urlopen(url))


def generate_invite_qr_img(qrcode_url, avatar_url, params, save_path=None, bg_file=None):
    """
    生成邀请代理的图片
    :param qrcode_url: 参数二维码的链接
    :param avatar_url: 头像链接
    :param params:
        params=dict(name=u'周先生(董事)', invite=u'邀请您成为代理，级别“联发”')
        分别是第一句话, 第二句话
    :param save_path:
        保存路径
    :param bg_file:
    :return:
        返回None或者图片对象
    """
    qrimg = open_image_by_url(qrcode_url)
    qrimg.thumbnail((420, 420))
    from dj import settings
    bg = Image.open(bg_file or os.path.join(settings.BASE_DIR,
                                            'agents/images/bg_invite.jpg'))
    res = merge_image(bg, qrimg, (165, 438))
    if avatar_url:
        avatar = open_image_by_url(avatar_url)
        avatar.thumbnail((138, 138))
        res = merge(res, avatar, (306, 948))
    draw = ImageDraw.Draw(res)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR,
                                           'mall/images/simsun.ttc'), 30)
    draw.text((272, 1106), params['name'], (255, 255, 255), font=font)
    draw.text((192, 1160), params['invite'], (255, 255, 255), font=font)
    # if text:
    #     draw.text((210, 46), text.decode('utf-8') if isinstance(text, str) else text, (234, 106, 5), font=font)
    # draw.text((231, 82), u'立云在线', (234, 106, 5), font=font)
    if save_path:
        # res = res.resize(res.size, Image.ANTIALIAS)
        # res = res.convert('RGB')
        res.save(save_path)
        # res.save(save_path, optimize=True, quality=95)
    else:
        return res


def draw_text(draw, text, position, line_width, row_space, fill, font):
    """
    排版段落. 忽略了换行符
    :param draw:
    :param text: 文本内容
    :param position: 起点位置
    :param line_width: 行宽
    :param row_space: 行间距
    :param fill: 字体颜色
    :param font: 字体类型
    :return:
    """
    text = str(text)
    lw = line_width
    buf = []
    max_height = 0
    for t in text:
        if t == u'\n':
            continue
        width, height = font.getsize(t)
        max_height = max(max_height, height)
        lw -= width
        if lw > 0:
            buf.append(t)
        else:
            if lw == 0:
                buf.append(t)
            draw.text(position, u''.join(buf), fill, font=font)
            position = position[0], position[1] + row_space + max_height
            buf = []
            if lw < 0:
                buf.append(t)
                lw = line_width - width
            else:
                lw = line_width
    else:
        if buf:
            draw.text(position, u''.join(buf), fill, font=font)


def draw_text_new(draw, text, position, line_width, row_space, fill, font, segment_fills=None):
    """
    排版段落. 忽略了换行符
    :param segment_fills:
    [(start, stop, fill), ...]
    :param draw:
    :param text: 文本内容
    :param position: 起点位置
    :param line_width: 行宽
    :param row_space: 行间距
    :param fill: 字体颜色
    :param font: 字体类型
    :return:
    """
    # sfs = dict()
    # if segment_fills:
    #     for start, stop, fill in segment_fills:
    #         sfs.
    text = str(text)
    lw = line_width
    buf = []
    max_height = 0
    for t in text:
        if t == u'\n':
            continue
        width, height = font.getsize(t)
        max_height = max(max_height, height)
        lw -= width
        if lw > 0:
            buf.append(t)
        else:
            if lw == 0:
                buf.append(t)
            draw.text(position, u''.join(buf), fill, font=font)
            position = position[0], position[1] + row_space + max_height
            buf = []
            if lw < 0:
                buf.append(t)
                lw = line_width - width
            else:
                lw = line_width
    else:
        if buf:
            draw.text(position, u''.join(buf), fill, font=font)


CENTER_ALIGN = 0


def get_width_of_text(text, font):
    width = 0
    for t in text:
        width += font.getsize(t)[0]
    return width


def draw_text_align_complex(draw, texts, line_width, row_space, top, horizonal_alignment=CENTER_ALIGN):
    """

    :param draw:
    :param texts:
    [(text, font, fill, top_offset), ...]
    :param line_width:
    :param row_space:
    :param top:
    :param horizonal_alignment:
    :return:
    """
    length = 0
    prepares = []
    offset = 0
    for text, font, fill, top_offset in texts:
        width = get_width_of_text(text, font)
        length += width
        prepares.append((text, font, fill, top_offset, offset))
        offset += width
    position = (line_width - length) / 2, top
    for text, font, fill, top_offset, offset in prepares:
        draw_text(draw, text, (position[0] + offset, position[1] + top_offset), line_width, row_space, fill, font)


def draw_text_align(draw, text, line_width, row_space, fill, font, top, horizonal_alignment=CENTER_ALIGN):
    """
    居中输入文本
    :param top: 上边距
    :param draw:
    :param text:
    :param line_width:
    :param row_space:
    :param fill:
    :param font:
    :param horizonal_alignment:
    :return:
    """
    length = get_width_of_text(text, font)
    position = (line_width - length) / 2, top
    return draw_text(draw, text, position, line_width, row_space, fill, font)


def draw_text_align_new(draw, text, line_width, row_space, fill, font, top, left):
    """
    居中输入文本
    :param top: 上边距
    :param draw:
    :param text:
    :param line_width:
    :param row_space:
    :param fill:
    :param font:
    :param horizonal_alignment:
    :return:
    """
    length = get_width_of_text(text, font)
    position = left + (line_width - length) / 2, top
    return draw_text(draw, text, position, line_width, row_space, fill, font)


def generate_cert(text, p2, p3, save_path=None):
    """
    代理授权证书
    :param text: 授权信息
    :param p2: 授权期限
    :param p3: 授权单位
    :param save_path:
    :return:
    """
    res = Image.open(os.path.join(settings.BASE_DIR,
                                  'agents/images/bg_cert.jpg'))

    # res = merge_image(res, res, (0, 0))

    draw = ImageDraw.Draw(res, 'RGBA')
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR,
                                           'mall/images/simsun.ttc'), 25)
    # draw.text((570, 1420), p1, (0x07, 0x09, 0x09), font=font)
    fill = (0x07, 0x09, 0x09)
    draw_text(draw, text, (162, 413), 516, 5, fill, font)
    draw.text((162, 628), p2, fill, font=ImageFont.truetype(os.path.join(settings.BASE_DIR,
                                                                         'mall/images/simsun.ttc'), 20))
    draw.text((400, 942), p3, fill, font=ImageFont.truetype(os.path.join(settings.BASE_DIR,
                                                                         'mall/images/simsun.ttc'), 20))

    if save_path:
        # res = res.resize(res.size, Image.ANTIALIAS)
        # res = res.convert('RGB')
        res.save(save_path)
        # res.save(save_path, optimize=True, quality=95)
    else:
        return res


def circle(img):
    ima = img.convert("RGBA")
    # ima = ima.resize((600, 600), Image.ANTIALIAS)
    size = ima.size
    print(size)

    # 因为是要圆形，所以需要正方形的图片
    r2 = min(size[0], size[1])
    if size[0] != size[1]:
        ima = ima.resize((r2, r2), Image.ANTIALIAS)

        # 最后生成圆的半径
    r3 = 90
    imb = Image.new('RGBA', (r3 * 2, r3 * 2), (255, 255, 255, 0))
    pima = ima.load()  # 像素的访问对象
    pimb = imb.load()
    r = float(r2 / 2)  # 圆心横坐标

    for i in range(r2):
        for j in range(r2):
            lx = abs(i - r)  # 到圆心距离的横坐标
            ly = abs(j - r)  # 到圆心距离的纵坐标
            l = (pow(lx, 2) + pow(ly, 2)) ** 0.5  # 三角函数 半径

            if l < r3:
                pimb[i - (r - r3), j - (r - r3)] = pima[i, j]
    return imb


def generate_qrcode_cds(url, nickname, sequence, save_path=None, bg_file=None, avatar_url=None, plain=False):
    """
    cds mall share image. must save to png because alpha channel which only png has.
    只能输出为png, 不然处理不了圆形和透明
    use the jpg format to save is the smallest
    :param text: should be a str
    :param url:
    :param save_path:
    :param bg_file:
    :return:
    """
    child = generate(url, (220, 220))
    if plain:
        res = child
    else:
        import os
        from dj import settings
        from mp.models import ShareQrcodeBackground
        qr_bg = ShareQrcodeBackground.objects.filter(enable=True).first()
        bg_path = 'mall/images/share_cds_v3.jpg' if not qr_bg else qr_bg.image.path
        bg = Image.open(bg_file or os.path.join(settings.BASE_DIR,
                                                bg_path)).convert('RGBA')
        res = merge_image(bg, child, (490, 1030))
        if avatar_url:
            avatar = open_image_by_url(avatar_url)
            avatar = avatar.resize((120, 120))
            try:
                avatar = circle_thumbnail(avatar)
            except ValueError as e:
                if str(e) == "illegal image mode":
                    # 图片有问题
                    pass
            else:
                res = merge(res, avatar, (314, 726))
        draw = ImageDraw.Draw(res)
        font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 36)
        font2 = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 40)
        width, _ = bg.size
        # 绿色: (00, 0xc6, 00), 黑色: 0, 0, 0
        # draw_text_align(draw, str(sequence), width, 5, (0xf3, 0x3f, 0x40), font2, 915)
        # draw_text_align(draw, str(sequence), width, 5, (0xf3, 0x3f, 0x40), font2, 920)

        # draw_text_align_complex(draw, [(str(sequence), font2, (0xe6, 0, 0x39), 0)], width, 5, 870)
    # draw_text_align(draw, u'我是第3123812位推荐者', width, 5, (59, 57, 57), font, 1400)
    if save_path:
        # res = res.resize(res.size, Image.ANTIALIAS)
        # res = res.convert('RGB')
        res.save(save_path)
        # res.save(save_path, optimize=True, quality=95)
    else:
        return res


def circle_thumbnail(f):
    from PIL import Image, ImageOps, ImageDraw
    im = Image.open(f) if not isinstance(f, Image.Image) else f

    size = im.size
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)
    output = ImageOps.fit(im, mask.size, centering=(0.5, 0.5))
    output.putalpha(mask)
    return output


def gen_good_share_code(url, good, save_to):
    child = generate(url, (144, 144))
    gimg = Image.open(good.logo_mobile)
    gimg.thumbnail((560, 560))
    bg = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/share_good.jpg'))
    bg = merge_image(bg, gimg, (0, 0))
    bg = merge_image(bg, child, (386, 690))
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 35)
    draw = ImageDraw.Draw(bg)
    draw_text(draw, good.name, (30, 586), 500, 8, (0, 0, 0), font)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 50)
    draw_text(draw, '¥%s' % str(good.price), (40, 788), 200, 5, (0xff, 0x4b, 0x4b), font)
    bg.save(save_to)
    return True


def gen_get_qr_scene(user_id, save_to, bg, nickname=None, avatar_url=None, wxa_code=None, is_img=False):
    if not wxa_code:
        from mp.wechat_client import get_mp_client
        client = get_mp_client()
        data = client.get_qr_scene(user_id)
        code = open_image_by_url(data['url'])
    else:
        if is_img:
            code = wxa_code
        else:
            code = Image.open(wxa_code)
    code.thumbnail((220, 220))
    # res = merge(res, avatar, (50, 50))
    # child = generate(code, (136, 136))
    if not bg:
        bg = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/yykapp2.jpg'))
    else:
        bg = Image.open(bg)
    bg = merge_image(bg, code, (490, 1030))
    # logo = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/yykapplogo.jpg'))
    # bg = merge_image(bg, logo, (330, 380))
    draw = ImageDraw.Draw(bg)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 30)
    width, _ = bg.size
    # 绿色: (00, 0xc6, 00), 黑色: 0, 0, 0
    if nickname:
        draw_text(draw, nickname, (36, 900), width, 5, (0, 0, 0), font)
        # draw_text_align(draw, nickname, width, 5, (0, 0, 0), font, 466)
    if avatar_url:
        avatar = open_image_by_url(avatar_url)
        avatar.thumbnail((138, 138))
        bg = merge(bg, avatar, (306, 948))
    if save_to:
        bg.save(save_to)
    else:
        return bg


def gen_app_member_code(code, save_to=None, bg=None):
    child = generate(code, (220, 220))
    if not bg:
        bg = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/yykapp2.jpg'))
    else:
        bg = Image.open(bg)
    bg = merge_image(bg, child, (490, 1030))
    # logo = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/yykapplogo.jpg'))
    # bg = merge_image(bg, logo, (330, 380))
    if save_to:
        bg.save(save_to)
    else:
        return bg


# old
# def gen_app_member_code(code, save_to=None):
#     child = generate(code, (352, 352))
#     bg = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/yykapp2.jpg'))
#     bg = merge_image(bg, child, (198, 248))
#     logo = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/yykapplogo.jpg'))
#     bg = merge_image(bg, logo, (330, 380))
#     if save_to:
#         bg.save(save_to)
#     else:
#         return bg


def old_gen_app_member_code(code, save_to):
    child = generate(code, (444, 444))
    # gimg = Image.open(good.logo_mobile)
    # gimg.thumbnail((560, 560))
    bg = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/yykapp.jpg'))
    # bg = merge_image(bg, gimg, (0, 0))
    bg = merge_image(bg, child, (78, 178))
    # font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 35)
    # draw = ImageDraw.Draw(bg)
    # draw_text(draw, good.name, (30, 586), 500, 8, (0, 0, 0), font)
    # font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 50)
    # draw_text(draw, '¥%s'%624581597836557_.pic_hd.jpg str(good.price), (40, 788), 200, 5, (0xff, 0x4b, 0x4b), font)
    bg.save(save_to)
    return True


def show_share_wxa_code(wxa_code, save_to, show):
    """
    生成商品小程序分享码
    :param save_path:
    :param wxa_code: wxa_code_file
    :return:
    """
    child = Image.open(wxa_code)
    child.thumbnail((144, 144))
    gimg = Image.open(show.logo_mobile)
    gimg.thumbnail((560, 560))
    bg = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/share_good.jpg'))
    bg = merge_image(bg, gimg, (0, 0))
    bg = merge_image(bg, child, (386, 690))
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 35)
    draw = ImageDraw.Draw(bg)
    draw_text(draw, show.title, (30, 586), 500, 8, (0, 0, 0), font)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 50)
    draw_text(draw, show.get_show_type_display, (40, 788), 200, 5, (0xff, 0x4b, 0x4b), font)
    bg.save(save_to)


def good_share_wxa_code(wxa_code, save_to, show):
    """
    生成商品小程序分享码
    :param save_path:
    :param wxa_code: wxa_code_file
    :return:
    """
    child = Image.open(wxa_code)
    child.thumbnail((144, 144))
    gimg = Image.open(show.logo_mobile)
    gimg.thumbnail((560, 560))
    bg = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/share_good.jpg'))
    bg = merge_image(bg, gimg, (0, 0))
    bg = merge_image(bg, child, (386, 690))
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 35)
    draw = ImageDraw.Draw(bg)
    draw_text(draw, show.title, (30, 586), 500, 8, (0, 0, 0), font)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 50)
    draw_text(draw, show.get_show_type_display, (40, 788), 200, 5, (0xff, 0x4b, 0x4b), font)
    bg.save(save_to)


def good_thumbnail(url, save_to):
    """
    压缩第一张图片用于分享
    """
    gimg = open_image_by_url(url)
    gimg.thumbnail((160, 160))
    gimg.save(save_to)


if __name__ == '__main__':
    img = gen_app_member_code('aasdklasdklasdklasdklaslkdasldklasd1sd2')
    img.show()
    # avatar = '/Users/jacky/Downloads/i.jpg'
    # sf = '/Users/jacky/Downloads/x.png'
    # circle_thumbnail(avatar).save(sf)
    # image = Image.open(sf)
    # Image.composite(image, Image.new('RGB', image.size, 'white'), image).show()
    # Image.open(sf).show()
    # circle_new('/Users/jacky/Downloads/i.jpg').show()
    # avatar = 'http://thirdwx.qlogo.cn/mmopen/vi_32/4wty3YhJgbUNqUrP4MEEXMZufofIncPlv2yqsfNW9WLDJoYrHQzT9b7SsTPodZyu8liaKmpbtGfTSqSGUD5VQRw/132'
    # error image mode
    # avatar = 'http://thirdwx.qlogo.cn/mmopen/vi_32/DYAIOgq83er12KaiagAjtgm3BHIe5Csklswps3Lus1Q26glPfCyoDzibDyTcPSpXQKA33J3SbM5ac7NicOnKJiaXkw/132'
    # circle(open_image_by_url(avatar)).show()
    # generate_qrcode_cds('http://www.baidu.com', None, 1,
    #                     avatar_url=avatar, save_path='/Users/jacky/out.png')
    # print ImageFont.truetype(os.path.join(settings.BASE_DIR,
    #                                       'mall/images/simsun.ttc'), 30).getsize(u'a')
    # print '==='
    # generate_cert(u'    兹授权 林海 成为我公司代理,代理级别为董事,负责产品的销售和推广。手机号码为:13189096666', u'授权期限: 2017年12月28至2018年12月28',
    #               u'授权单位: 广州尚医生物科技有限公司').show()
    # generate_invite_qr_img(
    #     'https://mp.weixin.qq.com/cgi-bin/showqrcode?ticket=gQGL8DwAAAAAAAAAAS5odHRwOi8vd2VpeGluLnFxLmNvbS9xLzAyMFFjNXNxaXNjLTIxMDAwMHcwN2sAAgRU8yhaAwQAAAAA',
    #     'http://wx.qlogo.cn/mmopen/NyB7myqqYiaxpyQT4ib90zk3R5ibicKcjTH92SOmcstqaYRkd5KthsBRoqexQd1OiataylK8eaZcbAWcOh8XSJwaH1ZauDkbnjtUA/0'
    #     , params=dict(name=u'周先生(董事)', invite=u'邀请您成为代理，级别“联发”')).show()
    # generate_qrcode_ywyn('http://www.baidu.com').show()
    # generate_wc_qrcode('http://www.baidu.com', '方生',
    #                    'http://wx.qlogo.cn/mmopen/2Vhh7OvSibUDCFbwI42YmWHhFslMHgKY6h8GxDluERLicEX5ia9Lv9AbHeKCibjzYgP79Dp99fPJ0TnGDV1Fn96u2yxKZxFja7UO/132',
    #                    '/Users/jacky/out.jpg')

    # =======demo start======
    # gen img
    # child = generate('http://localhost.com', (234, 234),
    #                  '/Users/jacky/share.png')  # Image.open('/Users/jacky/share.png')
    # print child.size
    # bg = Image.open('/Users/jacky/work_git/lymall_platform/mall/images/share_bg.jpg')
    # res = merge_image(bg, child, (70, 846))
    # res.show()
    # =========demo stop=======
    # print bg.size
    # x, y = bg.size
    # icon_box = (70, 846, 70 + child.size[0], 846 + child.size[1])
    # print 'icon_box = ', icon_box
    # icon_img = _correct(child, icon_box)
    # print icon_img.size
    # icon_box = (245, 537, 395, 687)
    # nw = merge(bg, child, icon_box)
    # nw.save('/Users/jacky/out.png')
    # print generate('http://localhost.com', (410, 410), '/Users/jacky/share.png')


#     print generate('http://myq.liyunmall.com/static/front/mobile/html/index.html', (410, 410), '/Users/jacky/myq.png',
#                    icon='/Users/jacky/work_git/planc/mall/images/lmlogo.png')


def generate_protocol(sign_img, sign_time, background, save_path):
    bg = Image.open(background)
    sign = Image.open(sign_img)
    sign.thumbnail((350, 144))
    res = merge(bg, sign, (270, 290))
    draw = ImageDraw.Draw(res)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR,
                                           'mall/images/simsun.ttc'), 22)
    time = sign_time.strftime('%Y-%m-%d')
    draw.text((188, 254), time, (51, 51, 51), font=font)
    draw.text((188, 448), time, (51, 51, 51), font=font)
    if save_path:
        res.save(save_path)


def zcao_share_wxa_code(wxa_code, save_to, zcao, img=None):
    """
    生成商品小程序分享码
    :param save_path:
    :param wxa_code: wxa_code_file
    :return:
    """
    child = Image.open(wxa_code)
    child.thumbnail((144, 144))
    # if not img:
    img = 'mall/images/share_zcao.jpg'
    gimg = Image.open(os.path.join(settings.BASE_DIR, img))
    gimg.thumbnail((560, 560))
    bg = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/share_good.jpg'))
    bg = merge_image(bg, gimg, (0, 0))
    bg = merge_image(bg, child, (386, 690))
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 30)
    draw = ImageDraw.Draw(bg)
    title = zcao.body.decode("utf-8")
    if len(title) > 46:
        title = '{}...'.format(title[:47])
    draw_text(draw, title, (30, 586), 500, 8, (0, 0, 0), font)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 32)
    name = "匿名用户"
    if zcao.kol and zcao.kol.user:
        name = zcao.kol.user.get_full_name()
    name = name.decode("utf-8")
    if len(name) > 6:
        name = '{}...'.format(name[:7])
    draw_text(draw, name, (40, 788), 250, 5, (0, 0, 0), font)
    bg.save(save_to)


def show_share_wxa_code(wxa_code, save_to, show, flag_path=None, is_img=False):
    """
    生成商品小程序分享码
    :param save_path:
    :param wxa_code: wxa_code_file
    :return:
    """
    if not is_img:
        child = Image.open(wxa_code)
    else:
        child = wxa_code
    child.thumbnail((112 * 2, 112 * 2))
    if show.logo_mobile:
        gimg = Image.open(show.logo_mobile)
    else:
        from restframework_ext.exceptions import CustomAPIException
        raise CustomAPIException('没有封面')
    width = 375 * 2
    height = 510 * 2
    h = show.logo_mobile.height % 510
    w = show.logo_mobile.width % 375
    if h or w:
        gimg.resize((width, height), Image.ANTIALIAS)
    else:
        gimg.thumbnail((width, height))
    bg = Image.open(os.path.join(settings.BASE_DIR, 'mall/images/share_show.jpg'))
    bg = merge_image(bg, gimg, (0, 0))
    bg = merge_image(bg, child, (248 * 2, 529 * 2))
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 36)
    draw = ImageDraw.Draw(bg)
    title = show.title
    if len(show.title) > 11:
        title = title[:11] + '...'
    draw_text(draw, title, (15 * 2, 543 * 2), 227 * 2, 8, (0, 0, 0), font)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 26)
    # time_str = show.sale_time.strftime('%Y年%m月%d日 %H:%M开售')
    # draw_text(draw, time_str, (15 * 2, 565 * 2), 227 * 2, 5, (153, 153, 153), font)
    venue_title = show.venues.name
    draw_text(draw, venue_title, (15 * 2, 589 * 2), 227 * 2, 5, (153, 153, 153), font)
    if flag_path:
        flag = Image.open(flag_path)
        bg = merge_image(bg, flag, (15 * 2, 617 * 2))
    bg.save(save_to)


def save_code(code, save_to):
    bg = Image.open(code)
    bg.thumbnail((112 * 2, 112 * 2))
    bg.save(save_to)


def order_code_img(code_path, header, date_at, title, seat, code, venue, save_to):
    """
    生成商品小程序分享码
    :param save_path:
    :param wxa_code: wxa_code_file
    :return:
    """
    child = Image.open(code_path)
    child.thumbnail((320, 320))
    bg_path = 'ticket/images/ticket_code.png'
    bg = Image.open(os.path.join(settings.BASE_DIR, bg_path))
    bg = merge_image(bg, child, (141, 153 * 2))
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/simsun-bold.ttf'), 56)
    draw = ImageDraw.Draw(bg)
    draw_text(draw, header, (29, 15 * 2), 500, 8, (255, 255, 255), font)
    # draw_text(draw, '开演', (169, 27), 120, 8, (255, 255, 255), font)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 28)
    draw_text(draw, date_at, (29 + 4, 59 * 2), 500, 8, (255, 255, 255), font)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/simsun-bold.ttf'), 30)
    draw_text(draw, title, (29 + 5, 81 * 2), 281 * 2, 8, (255, 255, 255), font)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 28)
    # draw_text(draw, seat, (100*2, 138 * 2), 100 * 2, 8, (0, 0, 0), font)
    if seat:
        draw_text_align_new(draw, seat, 100 * 2, 5, (0, 0, 0), font, 130 * 2, 100 * 2)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 24)
    # draw_text(draw, code, (88*2, 334 * 2), 124 * 2, 8, (0, 0, 0), font)
    draw_text_align_new(draw, code, 124 * 2, 5, (0, 0, 0), font, 320 * 2, 88 * 2)
    draw_text_align_new(draw, '请勿截图给陌生人!', 117 * 2, 5, (153, 153, 153), font, 342 * 2, 183)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 28)
    draw_text_align_new(draw, venue, 200 * 2, 5, (0, 0, 0), font, 382 * 2, 68.5 * 2 - 25)
    bg.save(save_to)


def order_code_img_new(code_path, header, date_at, title, seat, code, venue, save_to, deadline_at=None):
    """
    生成商品小程序分享码
    :param save_path:
    :param wxa_code: wxa_code_file
    :return:
    """
    child = Image.open(code_path)
    child.thumbnail((320, 320))
    bg_path = 'ticket/images/ticket_code.png'
    if deadline_at:
        bg_path = 'ticket/images/ticket_code_new.png'
    bg = Image.open(os.path.join(settings.BASE_DIR, bg_path))
    bg = merge_image(bg, child, (141, 153 * 2))
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/simsun-bold.ttf'), 56)
    draw = ImageDraw.Draw(bg)
    draw_text(draw, header, (29, 15 * 2), 500, 8, (255, 255, 255), font)
    # draw_text(draw, '开演', (169, 27), 120, 8, (255, 255, 255), font)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 28)
    draw_text(draw, date_at, (29 + 4, 59 * 2), 500, 8, (255, 255, 255), font)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/simsun-bold.ttf'), 30)
    draw_text(draw, title, (29 + 5, 81 * 2), 281 * 2, 8, (255, 255, 255), font)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 28)
    # draw_text(draw, seat, (100*2, 138 * 2), 100 * 2, 8, (0, 0, 0), font)
    if seat:
        draw_text_align_new(draw, seat, 100 * 2, 5, (0, 0, 0), font, 130 * 2, 100 * 2)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 24)
    # draw_text(draw, code, (88*2, 334 * 2), 124 * 2, 8, (0, 0, 0), font)
    draw_text_align_new(draw, code, 150 * 2, 5, (0, 0, 0), font, 320 * 2, 72 * 2)
    draw_text_align_new(draw, '请勿截图给陌生人!', 117 * 2, 5, (153, 153, 153), font, 342 * 2, 183)
    font = ImageFont.truetype(os.path.join(settings.BASE_DIR, 'mall/images/huawen.ttf'), 28)
    draw_text_align_new(draw, venue, 200 * 2, 5, (0, 0, 0), font, 382 * 2, 68.5 * 2 - 25)
    if deadline_at:
        deadline_str = '有效期至:{}'.format(deadline_at)
        draw_text_align_new(draw, deadline_str, 200 * 2, 5, (0, 0, 0), font, 420 * 2, 68.5 * 2 - 25)
    bg.save(save_to)
    return bg_path

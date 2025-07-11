# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import requests
import logging
from caches import with_redis, get_redis, get_redis_name
from datetime import datetime
from common.utils import get_timestamp
import json
from common.config import get_config

logger = logging.getLogger(__name__)


class ApiAbstract(object):
    API_BASE_URL = 'https://pms.maitix.com/'

    def get_headers(self):
        raise NotImplementedError

    def get_cookies(self):
        raise NotImplementedError

    def eaders_key(self):
        raise NotImplementedError

    def cookies_key(self):
        raise NotImplementedError


class MaiZuo(ApiAbstract):
    #  麦座
    API_BASE_URL = 'https://pms.maitix.com/'

    def __init__(self, name, password):
        self.name = name
        self.password = password

    def login_key(self):
        return '{}_{}'.format(self.name, get_redis_name('maizou_login'))

    def headers_key(self):
        return '{}_{}'.format(self.name, get_redis_name('maizou_headers'))

    def cookies_key(self):
        return '{}_{}'.format(self.name, get_redis_name('maizou_cookies'))

    def project_key(self, session_id):
        return get_redis_name('maizou_project_{}'.format(session_id))

    def response_parse(self, resp):
        status = False
        ret = None
        if resp.status_code == 200:
            data = resp.json()
            if data['code'] == '200' and data['success']:
                status = True
                ret = data['data']
            else:
                logger.error('{}{}'.format(data['code'], data['msg']))
                if data['code'] == '17010010':
                    # 登录超时, 删除cookie
                    ret = False
                    with with_redis() as redis:
                        redis.delete(self.headers_key())
                        redis.delete(self.cookies_key())
        return status, ret

    def check_login(self):
        # 查看是否登录状态，cookies能否使用
        url = '{}pms/switch/checkProjectOpen'.format(self.API_BASE_URL)
        is_error = False
        try:
            resp = requests.get(url, headers=self.headers, cookies=self.cookies)
            status, ret = self.response_parse(resp)
        except Exception as e:
            logger.error(e)
            status = False
            is_error = True
        return status, is_error

    def login_task(self):
        config = get_config()
        mz_config = config['maizuo']
        url = mz_config['login_url']
        re_login_day = mz_config.get('re_login_day', 0)
        redis = get_redis()
        last_login_timestamp = redis.get(self.login_key())
        need_login = True
        status = True
        need_re_login = False
        if last_login_timestamp:
            # 一个小时检查一次是否登录过期
            need_login = int(last_login_timestamp) + 60 * 60 * 1000 < get_timestamp(datetime.now())
            if re_login_day > 0:
                need_re_login = int(last_login_timestamp) + int(re_login_day) * 24 * 60 * 60 * 1000 < get_timestamp(
                    datetime.now())
        if not need_re_login and need_login:
            # 如果过期会清空cookies
            status, is_error = self.check_login()
        # 如果过期会清空
        cookies = redis.get(self.cookies_key())
        is_fail = False
        if not cookies or not status or need_re_login:
            try:
                # resp = requests.get(url, params=dict(name=self.name, password=self.password))
                # if resp.status_code == 200:
                #     ret = resp.json()
                #     logger.warning(ret)
                #     if ret['code'] == 200:
                #         redis.set(self.headers_key(), json.dumps(ret['headers']))
                #         redis.set(self.cookies_key(), json.dumps(ret['cookies']))
                #         redis.set(self.login_key(), get_timestamp(datetime.now()))
                from maizuo.login import vcg_get_cookies
                st, headers, cookie, msg = vcg_get_cookies(name=self.name, password=self.password)
                if st:
                    redis.set(self.headers_key(), json.dumps(headers))
                    redis.set(self.cookies_key(), json.dumps(cookie))
                    redis.set(self.login_key(), get_timestamp(datetime.now()))
                else:
                    logger.error(msg)
                    is_fail = True
            except Exception as e:
                logger.error(e)
                is_fail = True
        if is_fail:
            from ticket.models import MaiZuoLoginLog
            MaiZuoLoginLog.create_record('登录失败', MaiZuoLoginLog.TY_LOGIN)

    @property
    def headers(self):
        with with_redis() as redis:
            headers = redis.get(self.headers_key())
            if headers:
                headers = json.loads(headers)
        return headers

    @property
    def cookies(self):
        with with_redis() as redis:
            cookies = redis.get(self.cookies_key())
            if cookies:
                cookies = json.loads(cookies)
        return cookies

    def get_project_id(self, show_name, start_at: datetime):
        url = '{}pms/project/getProjectComboBoxFuzzy'.format(self.API_BASE_URL)
        start_at_timestamp = get_timestamp(start_at)
        start_at = start_at.strftime("%Y-%m-%d %H%:M")
        params = dict(comboBoxCode=4, eventSaleState=2, projectStartTime=start_at, projectName=show_name)
        try:
            if not self.cookies:
                logger.error('未登录')
            else:
                resp = requests.get(url, params, headers=self.headers, cookies=self.cookies)
                status, data = self.response_parse(resp)
                if status and data:
                    for dd in data[0]['eventComboBoxVOList']:
                        if dd['eventShowStartTime'] == start_at_timestamp:
                            return data[0]['projectId'], dd['eventId']
                """
                 data:
                 {'eventComboBoxVOList': [{'eventId': '212567197',
                    'eventName': '2024-01-13 星期六 19:30',
                    'eventShowEndTime': 1705150800000,
                    'eventShowStartTime': 1705145400000,
                    'eventState': 2,
                    'name': '2024-01-13 星期六 19:30',
                    'ptnrId': '24235',
                    'siteId': '2596001',
                    'siteVersionId': '15750496',
                    'tenantId': '24235'}],
                  'isMx': 1,
                  'name': '【海口站】李波中式单口《李姐不理解》全国巡演@海口0113波波脱口秀',
                  'projectId': '218447018',
                  'projectName': '【海口站】李波中式单口《李姐不理解》全国巡演@海口0113波波脱口秀',
                  'ptnrId': '24235',
                  'seatType': 1,
                  'tenantId': '24235',
                  'venueId': '2596001'}
                 """
        except Exception as e:
            logger.error(e)
        return None, None

    def find_event_list(self, show_name, start_at: datetime):
        # 获取具体场次的id
        project_id, event_id = self.get_project_id(show_name, start_at)
        perform_template_id = None
        venue_id = None
        if project_id and event_id:
            url = '{}pms/event/findEventList'.format(self.API_BASE_URL)
            params = dict(projectId=project_id)
            try:
                resp = requests.get(url, params, headers=self.headers, cookies=self.cookies)
                status, data = self.response_parse(resp)
                if status and data and data['dataList']:
                    for dd in data.get('dataList'):
                        if start_at == datetime.strptime(dd['showStartTime'], '%Y/%m/%d %H:%M'):
                            perform_template_id = dd['siteVersionId']
                            venue_id = dd['siteId']
                            break
            except Exception as e:
                logger.error(e)
            return project_id, perform_template_id, venue_id, event_id
        else:
            logger.error('获取project_id失败')
            return None, None, None, None

    def get_stand_ids(self, project_id, perform_template_id, venue_id):
        url = '{}pms/ticket/produce/performTemplate/query'.format(self.API_BASE_URL)
        params = dict(performId=project_id, performTemplateId=perform_template_id, venueId=venue_id)
        stand_ids = []
        try:
            resp = requests.get(url, params, headers=self.headers, cookies=self.cookies)
            status, data = self.response_parse(resp)
            if status and data and data.get('editVenueTemplateSeatVO') and data['editVenueTemplateSeatVO'].get(
                    'templateContent'):
                dd = json.loads(data['editVenueTemplateSeatVO']['templateContent'])
                if dd.get('standList'):
                    for st in dd['standList']:
                        stand_ids.append(st['id'])
                return stand_ids
        except Exception as e:
            logger.error(e)
        return stand_ids

    def get_seat_data(self, show_name: str, start_at: datetime, maizuo_data: dict = None):
        stand_ids = None
        data = None
        if maizuo_data:
            project_id = maizuo_data['project_id']
            event_id = maizuo_data['event_id']
            perform_template_id = maizuo_data['perform_template_id']
            stand_ids = maizuo_data['stand_ids']
            venue_id = maizuo_data['venue_id']
        else:
            project_id, perform_template_id, venue_id, event_id = self.find_event_list(show_name, start_at)
            if event_id and perform_template_id and venue_id:
                stand_ids = self.get_stand_ids(event_id, perform_template_id, venue_id)
        if stand_ids:
            url = '{}pms/ticket/produce/seatData/query'.format(self.API_BASE_URL)
            params = dict(performId=event_id, performTemplateId=perform_template_id, venueId=venue_id,
                          standIds=stand_ids)
            try:
                resp = requests.post(url, json=params, headers=self.headers, cookies=self.cookies)
                status, data = self.response_parse(resp)
                if status:
                    if data.get("editStandSeatVO") and data["editStandSeatVO"].get("templateContent"):
                        from ticket.models import SessionSeat
                        content = data["editStandSeatVO"].get("templateContent")
                        content = content.replace('false', 'False')
                        content = content.replace('true', 'True')
                        content = content.replace('null', 'None')
                        content = eval(content)
                        """
                        seat = content[0]
                        # 未锁座需要 canOperate：True 才是可卖
                        seat['ticket']: {'canOperate': True, 'goodSaleState': 1, 'goodSaleStateMsg': '待销售',
                         'price': 780.0, 'priceColor': '#FD6566', 'priceId': '264012222', 'priceName': '互动专区780元',
                          'publishStatus': 20, 'ticketId': '737253565'}  
                        # 锁座 canOperate True ，存在lockTagId
                        {'canOperate': True, 'goodSaleState': 1, 'goodSaleStateMsg': '待销售', 'levelTagId': '11630023',
                         'lockEndTime': '', 'lockLevel':'5', 'lockLevelId': '5', 'lockStartTime': '2023-11-29 10:31', 'lockTagId': '14440095', 
                         'lockTagName': '暂锁', 'lockTime': '2023-11-29 10:31', 'lockTypeLabel': 'A', 'lockUser': '管理员', 
                         'lockVisible': True, 'price': 780.0, 'priceColor': '#FD6566', 'priceId': '264012222', 
                         'priceName': '互动专区780元', 'publishStatus': 20, 'ticketId': '737253568'}                  
                        """
                        dd = dict(event_id=event_id, project_id=project_id, venue_id=venue_id, stand_ids=stand_ids,
                                  perform_template_id=perform_template_id)
                        return content, dd
            except Exception as e:
                logger.error(e)
        else:
            logger.error('获取stand_ids失败')
        return None, data

    def query_seat_status(self, projectId: str, performanceId: str, standIds: list, areaInfoVersion=5):
        # 用于同步场次座位状态，暂时不使用
        """
        # 锁座 seatTags列表存在tagLevel非空，seatTags[0]必存在，saleStatus=2为可卖+tagLevel非空为锁座，status=8 为已售
        seats = {
            1914436784:{
              "seatTags": [
                {
                  "tagId": "11630024",
                  "tagStyle": null,
                  "lockEndTime": null,
                  "remark": "绘座绑定标签",
                  "tagName": "正座",
                  "tagLevel": null,
                  "operatorName": "管理员",
                  "tagDesc": null,
                  "operateBatchCode": "33992721",
                  "tagType": 7,
                  "lockStartTime": null,
                  "operatorId": "4399141754287",
                  "customer": null
                },
                {
                  "tagId": "11630023",
                  "tagStyle": null,
                  "lockEndTime": null,
                  "remark": null,
                  "tagName": "预留1级",
                  "tagLevel": 5,
                  "operatorName": "管理员",
                  "tagDesc": null,
                  "operateBatchCode": "33912976",
                  "tagType": 2,
                  "lockStartTime": 1701225115000,
                  "operatorId": "4399141754287",
                  "customer": null
                },
                {
                  "tagId": "14440095",
                  "tagStyle": "A",
                  "lockEndTime": null,
                  "remark": null,
                  "tagName": "暂锁",
                  "tagLevel": null,
                  "operatorName": "管理员",
                  "tagDesc": null,
                  "operateBatchCode": "33912976",
                  "tagType": 8,
                  "lockStartTime": 1701225115000,
                  "operatorId": "4399141754287",
                  "customer": null
                }
              ],
              "seatNum": "34",
              "rowNum": "8",
              "seatId": "1914436784",
              "saleStatus": 2,
              "rowId": "101290012"
            }
        }
        """
        url = '{}/pms/ticket/lock/querySeatStatus'.format(self.API_BASE_URL)
        params = {"projectId": projectId, "performanceId": performanceId, "areaInfoVersion": areaInfoVersion,
                  "standIds": standIds, "lstPerformId": [performanceId]}
        try:
            resp = requests.post(url, json=params, headers=self.headers, cookies=self.cookies)
            status, data = self.response_parse(resp)
            if status:
                if data.get('extResult') and data['extResult'].get('seats'):
                    seats = data['extResult'].get('seats')
                    return True, seats
        except Exception as e:
            logger.error(e)
        return False, None

    def ticket_lock(self, eventId, ticketIds, projectId, performTemplateId, remark):
        params = {"allOp": "2", "lockLevelId": "5", "lockTypeId": "14440095", "lockMark": remark, "lockEndTime": "",
                  "eventId": eventId, "ticketIds": ticketIds, "projectId": projectId,
                  "performTemplateId": performTemplateId}
        url = '{}pms/ticket/lock/mxTicketLock'.format(self.API_BASE_URL)
        try:
            resp = requests.post(url, json=params, headers=self.headers, cookies=self.cookies)
            status, data = self.response_parse(resp)
            return status
        except Exception as e:
            logger.error(e)
        return False

    def ticket_unlock(self, eventId: str, unlock_ticket_ids: list, projectId: str, performTemplateId: str):
        ticketIds = ','.join(unlock_ticket_ids)
        unLockTicketDTOList = []
        for ticket_id in unlock_ticket_ids:
            unLockTicketDTOList.append(
                {"ticketId": ticket_id, "tagIdList": ["11630023", "14440095"], "groupId": 0, "priceType": 0})
        params = {"allOp": "1", "eventId": eventId, "ticketIds": ticketIds, "projectId": projectId,
                  "unLockTicketDTOList": unLockTicketDTOList, "performTemplateId": performTemplateId}
        url = '{}pms/ticket/lock/mxTicketLock'.format(self.API_BASE_URL)
        try:
            resp = requests.post(url, json=params, headers=self.headers, cookies=self.cookies)
            status, data = self.response_parse(resp)
            return status
        except Exception as e:
            logger.error(e)
        return False


_mai_zuo_dict = dict()


def get_mai_zuo(name:str, password:str):
    global _mai_zuo_dict
    if not _mai_zuo_dict.get(name):
        _mai_zuo_dict[name] = MaiZuo(name, password)
    return _mai_zuo_dict[name]

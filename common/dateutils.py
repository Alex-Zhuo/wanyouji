# coding:utf-8

from datetime import timedelta
from datetime import datetime
from django.utils import timezone


def get_next_month():
    td = timezone.now().today()
    year, month, day = td.year, td.month, td.day
    if month == 12:
        month = 1
        year = year + 1
    else:
        month = month + 1
    return datetime(year=year, month=month, day=1)


def get_last_month():
    td = timezone.now()
    year, month, day = td.year, td.month, td.day
    if month == 1:
        month = 12
        year = year - 1
    else:
        month = month - 1
    return datetime(year=year, month=month, day=1)


def quarter_of_date(_date):
    return _date.year, (_date.month / 3 + (1 if _date.month % 3 else 0))


def monday_date_of(_date, week_offset=0):
    return _date + timedelta(days=7 - _date.weekday() + (week_offset - 1) * 7)


def date_from_str(date_str, format='%Y-%m-%d', return_none_when_format_invalid=False):
    try:
        return datetime.strptime(date_str, format).date()
    except ValueError as e:
        if return_none_when_format_invalid:
            return
        raise e


def get_month_day(year, month, day):
    now_date = datetime(year=year, month=month, day=day)
    if month == 12:
        month = 1
        year = year + 1
    else:
        month = month + 1
    return now_date, datetime(year=year, month=month, day=1)

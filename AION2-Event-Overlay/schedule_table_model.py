"""Finite dated and recurring per-weekday schedules; no GUI or network."""
import datetime as dt
import re

JST=dt.timezone(dt.timedelta(hours=9))
TABLE_KINDS=('weekly_times','dates')

def clock_text(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{2}:\d{2}(?::\d{2})?',value):
        raise ValueError('時刻は HH:MM または HH:MM:SS で指定してください')
    at=dt.time.fromisoformat(value)
    return at.strftime('%H:%M:%S' if at.second else '%H:%M')

def table_schedule(kind,table):
    if kind not in TABLE_KINDS or not isinstance(table,dict):raise ValueError('予定表の形式を確認してください')
    result={}
    for key,values in table.items():
        if kind=='weekly_times':
            if not isinstance(key,str) or key not in tuple(str(n) for n in range(7)):
                raise ValueError('曜日は月曜0〜日曜6で指定してください')
        else:
            if not isinstance(key,str) or dt.date.fromisoformat(key).isoformat()!=key:
                raise ValueError('日付は YYYY-MM-DD で指定してください')
        if not isinstance(values,list):raise ValueError('各日の時刻はリストで指定してください')
        clocks=sorted(set(clock_text(value) for value in values))
        if clocks:result[key]=clocks
    if not result:raise ValueError('時刻を1つ以上追加してください。通知を止める場合はベルをOFFにしてください')
    return {'kind':kind,'table':dict(sorted(result.items())),'utc_offset':9,'edited':True}

def validate_table(s):
    table_schedule(s['kind'],s.get('table'))
    if s.get('utc_offset',9)!=9:raise ValueError('日付別・曜日別の予定は日本時間（UTC+9）です')

def next_table_occurrence(s,now):
    local=now.astimezone(JST);candidates=[]
    if s['kind']=='dates':
        days=((dt.date.fromisoformat(day),values) for day,values in s['table'].items())
    else:
        days=((local.date()+dt.timedelta(days=n),s['table'].get(str((local.weekday()+n)%7),[])) for n in range(8))
    for day,values in days:
        if day<local.date():continue
        for value in values:
            at=dt.datetime.combine(day,dt.time.fromisoformat(value),JST)
            if at>local:candidates.append(at)
    return min(candidates).astimezone(now.tzinfo) if candidates else None

def table_text(s):
    if s['kind']=='weekly_times':
        return '曜日別（毎週） '+ ' / '.join('月火水木金土日'[int(day)]+' '+','.join(values) for day,values in sorted(s['table'].items()))+' JST'
    count=sum(len(values) for values in s['table'].values())
    return f"日付別 {count}件・{min(s['table'])}〜{max(s['table'])} JST（期間後は終了）"

GARTUA_NOVEMBER_DATES={
    '2026-11-25':['20:30'], '2026-11-26':['07:30','18:30'],
    '2026-11-27':['05:30','16:30'], '2026-11-28':['03:30','14:30'],
    '2026-11-29':['01:30','12:30','23:30'], '2026-11-30':['10:30','21:30'],
    '2026-12-01':['08:30','19:30'], '2026-12-02':['06:30','17:30'],
}

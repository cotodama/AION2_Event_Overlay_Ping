"""Validated, second-precision schedule edits; no GUI, network or default resets."""
import copy
import datetime as dt
import math

JST=dt.timezone(dt.timedelta(hours=9))

def clock(value):
    return value.strftime('%H:%M:%S' if value.second else '%H:%M')

def local_datetime(value):
    parsed=dt.datetime.fromisoformat(str(value).strip())
    if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=JST)
    return parsed.astimezone(JST).replace(microsecond=0)

def minutes(value,minimum=0):
    number=float(value)
    if not math.isfinite(number) or not minimum<=number<=525600: raise ValueError('分数の範囲を確認してください')
    return number

def parse_windows(text):
    result=[]
    for pair in text.split(','):
        a,b=pair.strip().split('-',1)
        aa,bb=dt.time.fromisoformat(a.strip()),dt.time.fromisoformat(b.strip())
        if aa.tzinfo or bb.tzinfo or aa==bb: raise ValueError('開催時間帯を確認してください')
        result.append([aa.isoformat(),bb.isoformat()])
    if not result: raise ValueError('開催時間帯が必要です')
    return result

def event_edit(original,name,mode,target,interval,days,windows,entry,duration):
    if not name.strip(): raise ValueError('名前を入力してください')
    value=copy.deepcopy(original);value.update(name_ja=name.strip(),emoji_in_name=True)
    if mode=='keep': return value
    if mode=='unknown':
        value.update(schedule_confirmed=False,schedule_edited=True,schedule_note='未確認');return value
    at=local_datetime(target)
    value.update(type=mode,schedule_confirmed=True,schedule_edited=True,schedule_reference='user',
        schedule_note='ユーザー編集（JST）',entry_minutes=minutes(entry),duration_minutes=minutes(duration))
    value.pop('interval_anchor',None)
    if mode=='interval':value.update(start=clock(at),interval_minutes=minutes(interval,.5),interval_anchor=at.isoformat())
    elif mode=='once':value['at']=at.isoformat()
    elif mode=='daily':value['start']=clock(at)
    elif mode=='weekly':
        if not days or any(n not in range(7) for n in days):raise ValueError('曜日を選択してください')
        value.update(weekdays=list(days),times=[clock(at)])
    elif mode=='windows':value['windows']=parse_windows(windows)
    else:raise ValueError('予定の種類を選んでください')
    return value

def boss_schedule(mode,target,interval,days):
    if mode=='unknown':return None
    at=local_datetime(target)
    if mode=='interval':return dict(kind=mode,anchor=at.isoformat(),minutes=minutes(interval,.5),edited=True)
    if mode=='once':return dict(kind=mode,at=at.isoformat(),edited=True)
    if mode in ('daily','weekly'):
        value=dict(kind=mode,time=clock(at),utc_offset=9,edited=True)
        if mode=='weekly':
            if not days or any(n not in range(7) for n in days):raise ValueError('曜日を選択してください')
            value['weekdays']=list(days)
        return value
    raise ValueError('予定の種類を選んでください')

def edited_event_status(e,now):
    from event_model import occurrences,next_start
    if not e.get('schedule_confirmed',True):return 'unknown',0,None
    now=now.astimezone(JST)
    if e['type']=='interval':
        anchor=local_datetime(e['interval_anchor']) if e.get('interval_anchor') else dt.datetime.combine(dt.date(1970,1,1),dt.time.fromisoformat(e['start']),JST)
        span=dt.timedelta(minutes=float(e['interval_minutes']))
        previous=[anchor+span*((now-anchor)//span)] if now>=anchor else []
    elif e['type']=='once':
        at=local_datetime(e['at']);previous=[at] if at<=now else []
    else:previous=occurrences(e,now-dt.timedelta(days=8),now)
    if previous:
        start=previous[-1]
        if e['type']=='windows':
            for a,b in e.get('windows',[]):
                begin=dt.datetime.combine(start.date(),dt.time.fromisoformat(a),JST)
                end=dt.datetime.combine(start.date(),dt.time.fromisoformat(b),JST)
                if end<=begin:end+=dt.timedelta(days=1)
                if begin<=now<end:return 'active',0,(end-now).total_seconds()
        else:
            entry=dt.timedelta(minutes=float(e.get('entry_minutes',0)))
            duration=dt.timedelta(minutes=float(e.get('duration_minutes',0)))
            if entry and now<start+entry:return 'entry',(start+entry-now).total_seconds(),(start+entry-now).total_seconds()
            if duration and now<start+duration:return 'active',0,(start+duration-now).total_seconds()
    nxt=next_start(e,now)
    return ('next',(nxt-now).total_seconds(),None) if nxt else ('finished',0,None)

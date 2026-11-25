"""Portable event migration and notification boundaries; no GUI or network."""
import copy
import datetime as dt
import uuid
import re

JST = dt.timezone(dt.timedelta(hours=9))
EMOJI = {'Spacetime Rift':'🌌', 'Shugo Festa':'🦊', 'Dimensional Invasion':'🌀⚔️', 'Artifact Siege':'🌀🏰'}
KNOWN_IDS = {'Spacetime Rift':'rift', 'Shugo Festa':'shugo', 'Battlefield':'battlefield',
             'Artifact Siege':'artifact', 'Dimensional Invasion':'dimensional-invasion'}

def migrate_config(config):
    c = copy.deepcopy(config)
    first = int(c.get('event_schema', 0)) < 2
    c.setdefault('show_event_emoji', True)
    c.setdefault('event_compact', False)
    ids=set()
    for e in c.get('events', []):
        kind = e.get('name_en')
        e.setdefault('id', KNOWN_IDS.get(kind) or 'custom-'+uuid.uuid4().hex)
        if not e['id'] or e['id'] in ids: e['id']='custom-'+uuid.uuid4().hex
        ids.add(e['id'])
        e.setdefault('alert_enabled', True)
        e.setdefault('sound_enabled', True)
        e.setdefault('sound_file', '')  # empty inherits the existing global sound
        e.setdefault('sound_volume', None)
        if 'schedule_confirmed' not in e:
            untouched = (kind=='Spacetime Rift' and e.get('start')=='02:00' and e.get('interval_minutes')==180) or (
                kind=='Artifact Siege' and e.get('weekdays')==[2,5] and e.get('times')==['21:00']) or (
                kind=='Battlefield' and e.get('windows')==[['11:00','14:00'],['19:00','21:00']])
            e['schedule_confirmed'] = not untouched
            e['schedule_note'] = '未確認（旧初期値）' if untouched else 'ユーザー登録値（公式未確認）'
        if first and kind=='Shugo Festa':
            e.update(start='00:00', interval_minutes=60, entry_minutes=3,
                     notify_before_minutes=0, alert_timing='start_only', schedule_confirmed=True,
                     schedule_note='ユーザー指定：毎時00分 / 入場3分')
        if first and kind=='Artifact Siege':
            e.update(notification_leads=[40,30,0], alert_timing='both')
    if first and not any(e.get('name_en')=='Dimensional Invasion' or e.get('name_ja')=='次元侵攻' for e in c.get('events', [])):
        c.setdefault('events', []).append(dict(id='dimensional-invasion', name_ja='次元侵攻', name_en='Dimensional Invasion',
            type='interval', start='00:30', interval_minutes=60, entry_minutes=0, enabled=True,
            alert_enabled=True, sound_enabled=True, sound_file='', sound_volume=None,
            notify_before_minutes=0, alert_timing='start_only', schedule_confirmed=True,
            schedule_note='ユーザー指定：毎時30分',
            description='陣営のフィールド／ゲーム内の次元侵攻アイコンをタップして入場'))
    if c.get('schedule_update_134')!=True:
        for e in c.get('events',[]):
            if e.get('name_en')=='Artifact Siege':
                e.update(type='weekly',weekdays=[0,3,5],times=['21:00'],schedule_confirmed=True,
                    notification_leads=[40,30,0],notify_before_minutes=40,alert_timing='both',
                    schedule_note='ユーザー指定：月・木・土21:00 JST（20:20入場推奨）',schedule_reference='user')
        c['schedule_update_134']=True
    if not c.get('schedule_update_137'):
        for e in c.get('events',[]):
            if e.get('name_en')=='Artifact Siege' or e.get('id')=='artifact':
                e.update(type='weekly',weekdays=[3,5],times=['21:00'],schedule_confirmed=True,
                    schedule_note='2026-11-04提供の変更案内：木・土21:00 JST（20:20入場推奨）')
        c['schedule_update_137']=True
    c['event_schema'] = 2
    for e in c.get('events',[]):
        if e.get('name_en') in ('Spacetime Rift','Battlefield') and e.get('schedule_note')=='未確認（旧初期値）':
            e['schedule_confirmed']=True
            e['schedule_note']='日本／Global参考予定（公開時間表、2026-10-12確認／ゲーム内出現は未確認）'
            e['schedule_source']='https://www.aion2timers.com/schedule/'
            e['schedule_reference']='community'
            if e['name_en']=='Spacetime Rift': e.update(start='02:00',interval_minutes=180,entry_minutes=0)
            else: e['windows']=[['11:00','14:00'],['19:00','21:00']]
        if e.get('emoji_in_name'): continue
        prefix=e.get('emoji') or EMOJI.get(e.get('name_en'),'')
        for field in ('name_ja','name_en_display'):
            name=e.get(field,e.get('name_en','') if field=='name_en_display' else '')
            e[field]=(prefix+' ' if prefix and not name.startswith(prefix) else '')+name
        e['emoji_in_name']=True
    return c

def without_emoji(name):
    # Hide pictographs and their variation/joining marks; retain ordinary text.
    name=re.sub(r'[0-9#*]\ufe0f?\u20e3','',name)
    return re.sub(r'[\U0001f000-\U0001faff\u2600-\u27bf\u2300-\u23ff\u2b00-\u2bff\ufe0f\u200d\u20e3]','',name).strip()

def event_name(e, language='ja', emoji=True):
    name = (e.get('name_en_display') or e.get('name_en') or e.get('name_ja') or 'Event') if language=='en' else (e.get('name_ja') or e.get('name_en') or 'イベント')
    if e.get('emoji_in_name'):
        return name if emoji else without_emoji(name)
    prefix = e.get('emoji') or EMOJI.get(e.get('name_en'), '')
    return (prefix+' ' if prefix and not name.startswith(prefix) else '')+name if emoji else without_emoji(name)

def hm(value):
    h,m = map(int, str(value).split(':'))
    if not 0<=h<=23 or not 0<=m<=59: raise ValueError('HH:MMを入力してください')
    return h,m

def occurrences(e, begin, end):
    """Inclusive starts in a bounded JST range; interval starts cross midnight."""
    if not e.get('schedule_confirmed', True): return []
    begin=begin.astimezone(JST); end=end.astimezone(JST)
    if end<begin: return []
    typ=e.get('type','daily'); result=[]
    if typ=='once':
        at=dt.datetime.fromisoformat(e['at']).astimezone(JST)
        return [at] if begin<=at<=end else []
    if typ=='interval':
        anchor=(dt.datetime.fromisoformat(e['interval_anchor']).astimezone(JST) if e.get('interval_anchor') else
                dt.datetime.combine(dt.date(1970,1,1),dt.time.fromisoformat(e.get('start','00:00')),JST))
        span=dt.timedelta(minutes=max(.5,float(e.get('interval_minutes',60))))
        n=(begin-anchor)//span
        if e.get('interval_anchor'):n=max(0,n)
        candidate=anchor+n*span
        if candidate<begin: candidate+=span
        while candidate<=end:
            result.append(candidate); candidate+=span
        return result
    date=begin.date()
    while date<=end.date():
        if typ=='weekly' and date.weekday() not in e.get('weekdays', []):
            date+=dt.timedelta(days=1); continue
        values=([w[0] for w in e.get('windows', [])] if typ=='windows' else
                e.get('times', []) if typ=='weekly' else [e.get('start','00:00')])
        for value in values:
            candidate=dt.datetime.combine(date,dt.time.fromisoformat(value),JST)
            if begin<=candidate<=end: result.append(candidate)
        date+=dt.timedelta(days=1)
    return sorted(set(result))

def notification_leads(e):
    if e.get('name_en') in ('Shugo Festa','Dimensional Invasion'): return [0]
    if e.get('name_en')=='Artifact Siege': return [40,30,0]
    if e.get('notification_leads') is not None:
        leads=[int(n) for n in e['notification_leads']]
        if any(n<0 or n>10080 for n in leads): raise ValueError('通知は0〜10080分です')
        return sorted(set(leads),reverse=True)
    n=max(0,int(e.get('notify_before_minutes',0)))
    return [n,0] if n and e.get('alert_timing','both')=='both' else [0]

def due_notifications(e, previous, now):
    if previous is None or now<previous or not e.get('enabled',True) or not e.get('alert_enabled',True): return []
    leads=notification_leads(e)
    # Do not replay historical alerts after sleep; retain a short delayed tick.
    begin=max(previous, now-dt.timedelta(minutes=5))
    starts=occurrences(e,begin,now+dt.timedelta(minutes=max(leads)))
    result=[]
    for start in starts:
        for lead in leads:
            due=start-dt.timedelta(minutes=lead)
            if begin<due<=now:
                token=f"{e['id']}|{start.isoformat()}|{lead}"
                result.append((token,start,lead))
    return result

def next_start(e, now):
    if not e.get('schedule_confirmed',True):return None
    if e.get('type')=='once':
        at=dt.datetime.fromisoformat(e['at']).astimezone(JST)
        return at if at>now else None
    if e.get('type')=='interval' and e.get('interval_anchor'):
        anchor=dt.datetime.fromisoformat(e['interval_anchor']).astimezone(JST)
        span=dt.timedelta(minutes=max(.5,float(e['interval_minutes'])))
        return anchor+span*max(0,(now-anchor)//span+1)
    values=occurrences(e,now-dt.timedelta(days=1),now+dt.timedelta(days=8))
    return next((x for x in values if x>now),None)

def notification_text(e, start, lead, emoji=True):
    from schedule_edit_model import clock
    name=event_name(e,emoji=emoji)
    text=f"{name} {clock(start.astimezone(JST))} JST 開始"
    if e.get('name_en')=='Shugo Festa':
        closing=start+dt.timedelta(minutes=float(e.get('entry_minutes',3)))
        nxt=next_start(e,start) if e.get('schedule_edited') else start+dt.timedelta(hours=1)
        text+=f" / 入場締切 {clock(closing)} JST\n次回 {clock(nxt)+' JST' if nxt else '予定なし'}\n🔔 開始予定時刻"
    elif e.get('name_en')=='Dimensional Invasion':
        text+='\n陣営のフィールド／ゲーム内の次元侵攻アイコンをタップして入場\n🔔 開始予定時刻'
    elif e.get('name_en')=='Artifact Siege' and lead:
        text+=f"（{lead}分前）\n混雑が予想されます。早めの入場を準備してください。"
    else: text+='\n🔔 開始予定時刻' if not lead else f'（{lead}分前）'
    return text

"""Tracker definitions and clock logic, independent of Tk and network access."""
import copy
import datetime as dt
import json
import math
from pathlib import Path
from urllib.parse import urlparse

UTC = dt.timezone.utc
UNKNOWN = '未確認'
MAPS = 'https://aion2.gaming.tools/ja/maps'
NPCS = 'https://aion2.gaming.tools/ja/npcs'

def safe_link(url):
    p = urlparse(url or '')
    return p.scheme == 'https' and p.netloc == 'aion2.gaming.tools' and p.path.startswith('/ja/')

def defaults():
    stages = [900, 1000, 1400, 1600, 1900, 2000, 2100]
    hints = [
        'Lv45クエストの残り、激突ルーン、覚醒を確認。未取得の腕輪・ベルト・アミュレットを確認。',
        '羽根・モノリス・ディーヴァニオンと装備の空き枠を確認。素材の予算を決めて不足分を強化。',
        '征服の参加条件をゲーム内で確認。バクロン等の報酬とオード消費を比較。',
        '超越・アルカナの参加条件をゲーム内で確認。装備更新と恒久育成を並行。',
        '低い部位から更新。魔石・スキル・ディーヴァニオンの不足を確認。',
        '2100に向けて不足部位を絞り、週の残り回数と素材を確認。',
        '解放された征服等の参加条件を確認。次の装備更新と週課を計画。']
    il = [dict(id=f'il-{s}', name=f'IL {s}'+('+' if s==2100 else ''), hint=h,
               map_url=MAPS, npc_url=NPCS, note='ユーザー指定の育成目安。解放条件・最適手順は未確認。')
          for s,h in zip(stages,hints)]
    daily = ['デイリークエスト／依頼', '日次ダンジョンの残り回数', 'オードエネルギーと上限',
             '征服・超越の蓄積回数', '悪夢の残り回数', 'シューゴフェスタ', '時空の亀裂']
    weekly = ['ウィークリークエスト／依頼', 'アビス補給依頼', '征服の週間報酬・天井',
              '超越の週間報酬', 'レギオンの週間活動', '週間ショップ・交換']
    tasks = {k:[dict(id=f'{k}-{i}',name=n,map_url=MAPS,npc_url=NPCS,
                       note='確認用チェックリスト。回数・報酬・リセット時刻は未確認。')
                 for i,n in enumerate(names)] for k,names in [('daily',daily),('weekly',weekly)]}
    bosses=[]
    for ident,name,faction,area,npc,mapid in [
        ('gartua-elyos','永遠のガルトゥア','天族','ベルテロン / 永遠の島','2101074','1010'),
        ('gartua-asmo','不滅のガルトゥア','魔族','アルトガルド / 不滅の島','2400800','1110')]:
        bosses.append(dict(id=ident,name=name,faction=faction,area=area,equipment_il='70',
            drops='ガルトゥアのプレート・ゲートル等',coordinates=None,coordinate_source='',
            map_url=f'{MAPS}/{mapid}',npc_url=f'{NPCS}/{npc}',schedule=None,
            source='https://aion2.gaming.tools/ja/items/210230060',checked_at='2026-10-06',
            note='装備ILは個別装備の値。出現時刻・間隔・座標は未確認。'))
    return dict(schema=1,il=il,**tasks,bosses=bosses,
                resets={'daily':None,'weekly':None})

def validate_schedule(s):
    if s is None: return
    if not isinstance(s,dict): raise ValueError('予定はオブジェクトまたはnullです')
    if s.get('kind') in ('weekly_times','dates'):
        from schedule_table_model import validate_table
        validate_table(s)
    elif s.get('kind')=='once':
        at=dt.datetime.fromisoformat(s['at'])
        if at.tzinfo is None:raise ValueError('日時にUTCオフセットが必要です')
    elif s.get('kind')=='interval':
        anchor=dt.datetime.fromisoformat(s['anchor'])
        if anchor.tzinfo is None: raise ValueError('基準日時にUTCオフセットが必要です')
        if not .5 <= float(s['minutes']) <= 525600: raise ValueError('間隔は0.5〜525600分です')
    elif s.get('kind') in ('daily','weekly'):
        values=s.get('times',[s['time']])
        if not isinstance(values,list) or not values:raise ValueError('時刻を1つ以上指定してください')
        for value in values:
            parsed=dt.time.fromisoformat(value)
            if parsed.tzinfo is not None: raise ValueError('時刻にUTC差は含めないでください')
        if not -12 <= float(s['utc_offset']) <= 14: raise ValueError('UTC差は-12〜14です')
        if s['kind']=='weekly':
            days=s.get('weekdays',[s.get('weekday')])
            if not isinstance(days,list) or not days or any(not 0<=int(n)<=6 for n in days): raise ValueError('曜日は0(月)〜6(日)です')
    else: raise ValueError('形式はdaily / weekly / intervalです')

def next_occurrence(s, now):
    if not s: return None
    validate_schedule(s)
    if s['kind'] in ('weekly_times','dates'):
        from schedule_table_model import next_table_occurrence
        return next_table_occurrence(s,now)
    if s['kind']=='once':
        at=dt.datetime.fromisoformat(s['at']).astimezone(UTC)
        return at if at>now else None
    if s['kind']=='interval':
        anchor=dt.datetime.fromisoformat(s['anchor']).astimezone(UTC)
        span=dt.timedelta(minutes=float(s['minutes']))
        count=max(0,math.floor((now-anchor)/span)+1)
        return anchor+span*count
    zone=dt.timezone(dt.timedelta(hours=float(s['utc_offset'])))
    local=now.astimezone(zone)
    if s['kind']=='daily':
        targets=[dt.datetime.combine(local.date(),dt.time.fromisoformat(t),zone) for t in s.get('times',[s['time']])]
        return min(t if t>local else t+dt.timedelta(days=1) for t in targets).astimezone(UTC)
    target=dt.datetime.combine(local.date(),dt.time.fromisoformat(s['time']),zone)
    if s['kind']=='weekly':
        values=[]
        for day in s.get('weekdays',[s.get('weekday')]):
            candidate=target+dt.timedelta(days=(int(day)-target.weekday())%7)
            if candidate<=local: candidate+=dt.timedelta(days=7)
            values.append(candidate)
        return min(values).astimezone(UTC)
    if target<=local: target+=dt.timedelta(days=7 if s['kind']=='weekly' else 1)
    return target.astimezone(UTC)

def period_key(s,now):
    nxt=next_occurrence(s,now)
    return nxt.isoformat() if nxt else 'manual'

def schedule_text(s):
    if not s: return UNKNOWN
    if s['kind'] in ('weekly_times','dates'):
        from schedule_table_model import table_text
        return table_text(s)
    if s['kind']=='once':return s['at']+' 今回のみ（登録値）'
    if s['kind']=='interval':
        seconds=round(float(s['minutes'])*60);hours,rest=divmod(seconds,3600);mins,secs=divmod(rest,60)
        period=f'{hours}時間'+(f'{mins}分' if mins else '')+(f'{secs}秒' if secs else '')
        return f"{s['anchor']} 基準 / {period}周期（登録値）"
    day=('・'.join('月火水木金土日'[int(n)] for n in s.get('weekdays',[s.get('weekday')]))+'曜 ') if s['kind']=='weekly' else '毎日 '
    return f"{day}{' / '.join(s.get('times',[s['time']]))} UTC{s['utc_offset']:+g}（登録値）"

def validate_catalog(c):
    if not isinstance(c,dict) or not isinstance(c.get('resets'),dict):
        raise ValueError('定義全体とresetsはオブジェクトです')
    ids=set()
    for group in ('il','daily','weekly','bosses'):
        if not isinstance(c.get(group),list): raise ValueError(f'{group}は配列です')
        for row in c[group]:
            if not isinstance(row,dict): raise ValueError('各項目はオブジェクトです')
            if not isinstance(row.get('id'),str) or not isinstance(row.get('name'),str):
                raise ValueError('IDと名前は文字列です')
            if not row.get('id') or row['id'] in ids: raise ValueError('IDは空欄不可・全体で一意です')
            ids.add(row['id'])
            if not row.get('name'): raise ValueError('名前が必要です')
            for key in ('map_url','npc_url'):
                if row.get(key) is not None and not isinstance(row.get(key),str): raise ValueError('リンクは文字列です')
                if row.get(key) and not safe_link(row[key]): raise ValueError('日本語gaming.toolsのHTTPSリンクが必要です')
            validate_schedule(row.get('schedule'))
            if row.get('coordinates') and not row.get('coordinate_source'):
                raise ValueError('座標には確認元が必要です')
    for group in ('daily','weekly'): validate_schedule(c['resets'].get(group))
    return c

class Tracker:
    def __init__(self,catalog,state):
        self.catalog=validate_catalog(catalog)
        self.state=state
        for key in ('checks','bells','leads','fired','periods'): state.setdefault(key,{})
        self.previous=None
        self.messages=[]

    def done(self,ident): return bool(self.state['checks'].get(ident))
    def checked(self,ident,value): self.state['checks'][ident]=bool(value)
    def bell(self,ident): return bool(self.state['bells'].get(ident,False))
    def lead(self,ident): return int(self.state['leads'].get(ident,5))

    def tick(self,now):
        changed=False; alerts=[]
        for group in ('daily','weekly'):
            key=period_key(self.catalog['resets'].get(group),now)
            old=self.state['periods'].get(group)
            if old and old!=key:
                for row in self.catalog[group]: self.checked(row['id'],False)
                changed=True
            if old!=key: self.state['periods'][group]=key; changed=True
        if self.previous is not None and now>=self.previous:
            for group in ('daily','weekly','bosses'):
                for row in self.catalog[group]:
                    ident=row['id']
                    if not self.bell(ident) or (group!='bosses' and self.done(ident)): continue
                    s=row.get('schedule') if group=='bosses' else self.catalog['resets'].get(group)
                    if not s: continue
                    # Shifting the lookup by lead time finds notifications even when
                    # the application was opened inside the pre-alert window.
                    lead=dt.timedelta(minutes=self.lead(ident))
                    occurrence=next_occurrence(s,self.previous+lead-dt.timedelta(microseconds=1))
                    if occurrence is None:continue
                    due=occurrence-lead
                    token=occurrence.isoformat()
                    if self.previous<=due<=now and self.state['fired'].get(ident)!=token:
                        self.state['fired'][ident]=token; changed=True
                        if row['name'] not in alerts:alerts.append(row['name'])
        self.previous=now
        if alerts: self.messages=alerts
        return changed,alerts

"""Public gaming.tools status data, shared by status and faction-balance views.

One background request per fifteen minutes. This is the same public Svelte JSON response
used by the referenced page; it needs no account, cookies or API credentials.
The display payload uses the site's client-side reverse/base64/XOR encoding.
Schema changes fail visibly rather than inventing population/status values.
"""
import base64
import json
import urllib.request
import urllib.error
import socket
import math

SOURCE_URL = 'https://aion2.gaming.tools/ja/server-status'
DATA_URL = SOURCE_URL + '/__data.json?x-sveltekit-invalidated=001'
FETCH_INTERVAL_SECONDS = 900

def next_fetch_deadline(monotonic_now,wall_now,manual_schedule=False):
    """Default quarter-hours; a manual refresh switches this session to 15m cadence."""
    delay=FETCH_INTERVAL_SECONDS if manual_schedule else FETCH_INTERVAL_SECONDS-(wall_now%FETCH_INTERVAL_SECONDS)
    return monotonic_now+delay

REGIONS = [('all','All regions'),('EU','Europe'),('NAW','NA West'),
           ('NAE','NA East'),('LA','SA'),('AS','Asia')]
PAIRS = [('Siel','Israphel'),('Nezekan','Zikel'),('Vaizel','Triniel'),
         ('Kaisinel','Lumiel'),('Yustiel','Marchutan'),('Ariel','Azphel'),
         ('Fregion','Ereshkigal'),('Meslamtaeda','Beritra'),('Hithanya','Nemon')]
PAIRING_SOURCE = 'https://store.steampowered.com/news/app/3393110/view/689769594581155928'

def decode_response(document):
    payload = None
    for node in document.get('nodes', []):
        if not isinstance(node, dict):
            continue
        data = node.get('data')
        if isinstance(data, list) and data and isinstance(data[0], dict):
            index = data[0].get('payload')
            if isinstance(index, int) and 0 <= index < len(data):
                payload = data[index]
        elif isinstance(data, dict):
            payload = data.get('payload')
        if isinstance(payload, str):
            break
    if not isinstance(payload, str):
        raise ValueError('サイトのJSON形式が変更されました')
    raw = base64.b64decode(payload[::-1], validate=True)
    key = bytes([154,60,87,241,40,189,100,14])
    result = json.loads(bytes(value ^ key[i % len(key)] for i, value in enumerate(raw)))
    validate_snapshot(result)
    return result

def validate_snapshot(result):
    if not isinstance(result, dict) or not isinstance(result.get('regions'), list):
        raise ValueError('地域データがありません')
    for region in result['regions']:
        if not isinstance(region, dict) or not isinstance(region.get('servers'), list):
            raise ValueError('サーバーデータがありません')
        for server in region['servers']:
            required = ('name','serverId','region','faction','load',
                        'isRunning','inMaintenance','creationBlocked','spark')
            if any(field not in server for field in required):
                raise ValueError('サーバー項目の形式が変更されました')
            for field in ('players','capacity','queue'):
                server.setdefault(field,None) # absent metrics are unknown, never zero
                if server[field] is not None and (not isinstance(server[field], (int,float)) or server[field] < 0):
                    raise ValueError('人口データが無効です')
            if server['load'] is not None and (not isinstance(server['load'],(int,float)) or isinstance(server['load'],bool) or not math.isfinite(server['load']) or server['load']<0):
                raise ValueError('混雑度データが無効です')
    return result

def fetch_snapshot():
    request = urllib.request.Request(DATA_URL, headers={
        'User-Agent':'AION2-Event-Overlay-Ping/1.4.0 (public JSON viewer)',
        'Accept':'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in (403,429):
            raise RuntimeError(f'HTTP {exc.code}: サイト側がJSON取得を拒否・制限しました。次回は15分後です') from exc
        raise RuntimeError(f'HTTP {exc.code}: JSON取得に失敗しました。次回は15分後です') from exc
    except (TimeoutError,socket.timeout) as exc:
        raise RuntimeError('JSONの応答が15秒以内に届きませんでした。次回は15分後です') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'JSONへの接続失敗: {exc.reason}。次回は15分後です') from exc
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('JSONのサイズが大きすぎます')
    try: document=json.loads(raw)
    except (ValueError,UnicodeDecodeError) as exc:
        raise RuntimeError('JSONではない応答を受信しました（HTML等への切り替えは行いません）') from exc
    return decode_response(document)

def filtered_servers(snapshot, region='all', search='', status='all'):
    servers = [s for r in snapshot.get('regions', []) for s in r['servers']
               if region == 'all' or s['region'] == region]
    if search:
        servers = [s for s in servers if search.casefold() in s['name'].casefold()]
    if status == 'online':
        servers = [s for s in servers if s['isRunning'] and not s['inMaintenance']]
    elif status == 'issues':
        servers = [s for s in servers if not s['isRunning'] or s['inMaintenance']]
    return servers

def status_label(server):
    return 'メンテナンス' if server['inMaintenance'] else 'オンライン' if server['isRunning'] else 'オフライン'

def balance_groups(snapshot, region='all', search=''):
    """Pair by published names, never by list order or a guessed server ID."""
    groups=[]
    for r in snapshot.get('regions', []):
        if region != 'all' and r['code'] != region:
            continue
        worlds=r['servers']; pairs=[]; used=set()
        # Membership comes from the current JSON. An old per-region count must
        # not hide later servers that have an already published name pairing.
        for ename,aname in PAIRS:
            e=next((s for s in worlds if s['name']==ename and s['faction']=='Elyos'),None)
            a=next((s for s in worlds if s['name']==aname and s['faction']=='Asmodian'),None)
            for s in (e,a):
                if s: used.add(s['serverId'])
            if (e or a) and (not search or search.casefold() in (ename+' '+aname).casefold()):
                pairs.append((ename,aname,e,a))
        unpaired=[s for s in worlds if s['serverId'] not in used and
                  (not search or search.casefold() in s['name'].casefold())]
        totals={f:sum(s['players'] for s in worlds if s['faction']==f)
                if any(s['faction']==f for s in worlds) and all(s.get('players') is not None for s in worlds if s['faction']==f) else None
                for f in ('Elyos','Asmodian')}
        if pairs or unpaired:
            groups.append((r,totals,pairs,unpaired))
    return groups

def balance_fraction(elyos, asmodian):
    if elyos is None or asmodian is None or elyos + asmodian == 0:
        return None
    return elyos / (elyos + asmodian)

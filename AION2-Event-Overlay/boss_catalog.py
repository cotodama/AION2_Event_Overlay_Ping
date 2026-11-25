"""Source-checked additions, separate from UI. No guessed field respawns."""
from event_maps import mapped_url

def additional_bosses():
    rows=[]
    for ident,faction,area,npc,mapid in (
        ('ragta-elyos','天族','ベルテロン / ドラナ栽培地','2101131','1010'),
        ('ragta-asmo','魔族','アルトガルド / ラグタ要塞','2400853','1110')):
        rows.append(dict(id=ident,name='軍団長ラグタ',faction=faction,area=area,equipment_il='46',
            drops='ラグタのプレート・ゲートル・戦利品箱等',coordinates=None,coordinate_source='',
            map_url=mapped_url('軍団長ラグタ',mapid),npc_url='https://aion2.gaming.tools/ja/npcs/'+npc,
            schedule=None,source='https://aion2.gaming.tools/ja/items/210130105',checked_at='2026-10-12',
            note='育成途中の候補。確認したプレートはIL46（IL70ではありません）。出現時刻・再出現間隔は未確認。'))
    rows.append(dict(id='executor-argo',name='執行者アグロ',faction='天族・魔族',
        area='混沌のエレシュランタ下層 / シエルの翼の群島',equipment_il='70',
        drops='アグロのプレート・ゲートル等',coordinates=None,coordinate_source='',boss_type='abyss',
        map_url=mapped_url('執行者アグロ','20'),npc_url='https://aion2.gaming.tools/ja/npcs/2600097',
        schedule={'kind':'weekly','weekdays':[0,3,5],'time':'21:30','utc_offset':9},
        source='https://aion2.gaming.tools/ja/items/210130066',checked_at='2026-10-12',
        note='IL70防具の候補。DB記載の月・木・土21:30を日本サーバー時計として登録。ライブ在席・臨時変更は未確認。'))
    return rows

def upgrade_boss_catalog(catalog):
    if catalog.get('named_catalog_version',0)>=7:return False
    if catalog.get('named_catalog_version',0)>=6:return apply_weekday_update(catalog)
    if catalog.get('named_catalog_version',0)>=5:return apply_weekday_update(catalog)
    if catalog.get('named_catalog_version',0)>=4:return apply_weekday_update(catalog)
    if catalog.get('named_catalog_version',0)>=3:
        return apply_november_update(catalog)
    known={r['id'] for r in catalog['bosses']}
    # Only the original upgrade may add original rows; deleted bosses stay deleted.
    if catalog.get('named_catalog_version',0)<2:
        catalog['bosses'].extend(r for r in additional_bosses() if r['id'] not in known)
    for row in catalog['bosses']:
        if row['id'].startswith('gartua-'):
            row.update(schedule={'kind':'interval','anchor':'2026-10-01T05:00:00+09:00','minutes':720},
                schedule_display='05:00 / 17:00 JST・12時間周期（ユーザー指定）',
                note='ユーザー指定の参考予定。ゲーム内の現在の出現・臨時変更は未確認。')
        elif row['id'].startswith('ragta-'):
            row.update(schedule={'kind':'interval','anchor':'2026-10-01T05:10:00+09:00','minutes':720},
                schedule_display='05:10 / 17:10 JST・12時間周期（暫定）',
                note='ユーザー指定の参考予定（05:10 / 17:10、12時間周期）。DB両勢力ページに出現時刻掲載なし。公式時刻は未確認。装備IL46。')
    known={r['id'] for r in catalog['bosses']}
    catalog['bosses'].extend(r for r in abyss_bosses() if r['id'] not in known)
    return apply_november_update(catalog)

def apply_november_update(catalog):
    for row in catalog['bosses']:
        if row['id'].startswith(('gartua-','ragta-')):
            schedule=row.get('schedule') or {}
            if schedule.get('kind')=='interval' or row['id'].startswith('gartua-'):
                # Ragta keeps the player's anchor; Gartua has a supplied maintenance reference.
                row['schedule']=dict(schedule,kind='interval',minutes=660)
                if row['id'].startswith('gartua-'):
                    row['schedule']['anchor']='2026-11-04T18:30:00+09:00'
                row.pop('schedule_display',None)
                row['note']=('ユーザー提供の出現目安：2026-11-04 18:30 JST基準・11時間周期。実出現は未確認。編集で調整できます。'
                    if row['id'].startswith('gartua-') else '2026-11-04提供の変更案内：11時間周期。基準日時は保存済みの値（現在の実出現時刻は未確認）。編集で調整できます。')
        elif row['id']=='spirit-king-argo':
            if not row.get('display_name'):
                row['name']='精霊王アグロⅡ'
            row['schedule']={'kind':'daily','time':'10:30','times':['10:30','22:30'],'utc_offset':9}
            row['schedule_display']='毎日10:30 / 22:30 JST（2026-11-04提供の変更案内）'
            row['note']='ユーザー提供の変更案内：精霊王アグロⅡは毎日10:30 / 22:30 JST。実出現は未確認。既存アグロのMAP/NPCリンクを保持（Ⅱ専用NPCとの対応は未確認）。'
    catalog['named_catalog_version']=4
    return apply_weekday_update(catalog)

def apply_weekday_update(catalog):
    from schedule_table_model import GARTUA_NOVEMBER_DATES,table_schedule
    for row in catalog['bosses']:
        if row['id'].startswith('gartua-'):
            row['schedule']={'kind':'interval','anchor':'2026-11-25T20:30:00+09:00','minutes':660,'edited':True}
            row.pop('schedule_display',None)
            row['note']='ユーザー指定：2026-11-25 20:30 JST基準・11時間周期。12/2以降も周期で継続。メンテナンスで変わった場合は基準日時を編集してください。実出現は未確認。'
    catalog['named_catalog_version']=7
    return True

def abyss_bosses():
    rows=[]
    for ident,name,npc,place,il,drops,schedule,display,source in (
        ('spirit-king-argo','精霊王アグロ','2600068','シエルの翼の群島','70','アグロ防具',None,
         '出現時刻・周期：未確認','https://aion2.gaming.tools/ja/items/210530065'),
        ('executor-kaira','執行者カイラ','2600098','硫黄木の島','56','カイラ防具',
         {'kind':'weekly','weekdays':[0,3,5],'time':'21:30','utc_offset':9},
         '月・木・土21:30 JST（DB参考予定）','https://aion2.gaming.tools/ja/npcs/2600098'),
        ('watcher-kaira','監視者カイラ','2600089','黒い破片地帯ほか7か所','56','カイラ防具・英雄の証明関連功勲箱',
         {'kind':'interval','anchor':'2026-10-01T01:00:00+09:00','minutes':180},
         '01:00から3時間ごと JST（DB参考予定）','https://aion2.gaming.tools/ja/items/533700212'),
        ('guardian-nafma','守護神将ナフマ','2600084','エレシュランタの根','86','ナフマ防具・英雄の証明関連功勲箱',
         {'kind':'weekly','weekdays':[4,6],'time':'21:00','utc_offset':9},
         '金・日21:00 JST（DB参考予定）','https://aion2.gaming.tools/ja/items/533700297')):
        rows.append(dict(id=ident,name=name,faction='天族・魔族',area='混沌のエレシュランタ下層 / '+place,
            equipment_il=il,drops=drops,coordinates=None,coordinate_source='',boss_type='abyss',
            map_url=mapped_url(name,'20'),npc_url='https://aion2.gaming.tools/ja/npcs/'+npc,
            schedule=schedule,schedule_display=display,source=source,checked_at='2026-10-13',
            note='DB掲載のサーバー時刻をJSTとして登録。ライブ在席・数値座標は未確認。英雄の証明の直接ドロップは未確認。'))
    return rows

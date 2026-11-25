import datetime as dt
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from boss_catalog import upgrade_boss_catalog
from tracker_model import defaults,next_occurrence,Tracker
from event_model import migrate_config,JST,due_notifications,notification_text
from display_format import remaining_text

class UpdateTests(unittest.TestCase):
    def test_public_load_schema_does_not_invent_population(self):
        from server_data import validate_snapshot,balance_groups
        rows=[dict(name=name,serverId=n,region='AS',faction=faction,load=.4,isRunning=True,
            inMaintenance=False,creationBlocked=False,spark=[]) for n,name,faction in
            [(2501,'Israphel','Asmodian'),(2502,'Siel','Elyos')]]
        data={'regions':[{'code':'AS','servers':rows}]};validate_snapshot(data)
        self.assertIsNone(rows[0]['players']);self.assertIsNone(rows[0]['capacity']);self.assertIsNone(rows[0]['queue'])
        self.assertEqual(balance_groups(data,'AS')[0][1],{'Elyos':None,'Asmodian':None})
    def test_duration_boundaries(self):
        for sec,text in [(0,'0分'),(59,'1分'),(3540,'59分'),(3600,'1時間0分'),(13560,'3時間46分')]:
            self.assertEqual(remaining_text(sec),text)

    def test_field_schedule_no_double_notification(self):
        c=defaults();upgrade_boss_catalog(c)
        g=c['bosses'][0]
        for hour in (4,5,16,17,23):
            t=dt.datetime(2026,11,26,hour,0,tzinfo=JST)
            nxt=next_occurrence(g['schedule'],t).astimezone(JST)
            self.assertGreater(nxt,t);self.assertLessEqual(nxt-t,dt.timedelta(hours=11))
        row=next(r for r in c['bosses'] if r['id']=='ragta-asmo')
        t=dt.datetime(2026,10,13,7,17,tzinfo=JST)
        nxt=next_occurrence(row['schedule'],t)
        self.assertLessEqual(nxt-t,dt.timedelta(hours=11))
        tracker=Tracker(c,{'bells':{row['id']:True},'leads':{row['id']:0}})
        tracker.tick(nxt-dt.timedelta(seconds=1))
        self.assertEqual(tracker.tick(nxt)[1],['軍団長ラグタ']);self.assertEqual(tracker.tick(nxt)[1],[])

    def test_upgrade_respects_deletions_bells_checks_and_is_once(self):
        c=defaults();c.update(named_catalog_version=2);c['bosses']=[]
        upgrade_boss_catalog(c);self.assertEqual(len(c['bosses']),4)
        self.assertFalse(any(r['id'].startswith('gartua') for r in c['bosses']))
        before=copy.deepcopy(c);self.assertFalse(upgrade_boss_catalog(c));self.assertEqual(c,before)

    def test_artifact_weekday_and_shugo_kept(self):
        c=migrate_config({'events':[{'name_en':'Artifact Siege'},{'name_en':'Shugo Festa','name_ja':'シューゴフェスタ'}]})
        e=c['events'][0]
        for day in range(7):
            t=dt.datetime(2026,10,12+day,20,20,tzinfo=JST)
            self.assertEqual(bool(due_notifications(e,t-dt.timedelta(seconds=1),t)),day in (3,5))
        self.assertEqual(notification_text(c['events'][1],dt.datetime(2026,10,13,8,tzinfo=JST),0),
            '🦊 シューゴフェスタ 08:00 JST 開始 / 入場締切 08:03 JST\n次回 09:00 JST\n🔔 開始予定時刻')
        self.assertEqual(migrate_config(c),c)

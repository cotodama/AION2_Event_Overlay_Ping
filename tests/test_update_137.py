import copy
import datetime as dt
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from boss_catalog import upgrade_boss_catalog
from tracker_model import defaults,next_occurrence,Tracker,validate_schedule
from event_model import migrate_config,JST,due_notifications

class NovemberUpdateTests(unittest.TestCase):
    def test_existing_maintenance_anchor_ids_names_and_deletions_survive(self):
        c=defaults();c['named_catalog_version']=3
        row=c['bosses'][0]
        row.update(display_name='編集した名前',schedule={'kind':'interval','anchor':'2026-11-04T21:17:30+09:00','minutes':720,'edited':True})
        del c['bosses'][1]
        original=copy.deepcopy(row)
        self.assertTrue(upgrade_boss_catalog(c))
        self.assertEqual(len(c['bosses']),1)
        self.assertEqual(row['schedule']['kind'],'interval')
        self.assertEqual(row['schedule']['anchor'],'2026-11-25T20:30:00+09:00')
        self.assertEqual(row['schedule']['minutes'],660)
        self.assertEqual(row['display_name'],original['display_name'])
        after=copy.deepcopy(c);self.assertFalse(upgrade_boss_catalog(c));self.assertEqual(c,after)
        row['schedule']['minutes']=540
        self.assertFalse(upgrade_boss_catalog(c));self.assertEqual(row['schedule']['minutes'],540)

    def test_gartua_supplied_eight_day_reference_and_ragta_anchor(self):
        c=defaults();upgrade_boss_catalog(c)
        row=c['bosses'][0]
        now=dt.datetime(2026,11,25,20,29,tzinfo=JST)
        actual=[]
        for _ in range(16):
            now=next_occurrence(row['schedule'],now).astimezone(JST)
            actual.append(now.strftime('%d %H:%M'))
        self.assertEqual(actual,['25 20:30','26 07:30','26 18:30','27 05:30','27 16:30','28 03:30','28 14:30',
            '29 01:30','29 12:30','29 23:30','30 10:30','30 21:30','01 08:30','01 19:30','02 06:30','02 17:30'])
        c={'named_catalog_version':3,'bosses':[{'id':'ragta-asmo','schedule':{
            'kind':'interval','anchor':'2026-11-04T19:17:30+09:00','minutes':720}}]}
        upgrade_boss_catalog(c)
        self.assertEqual(c['bosses'][0]['schedule']['anchor'],'2026-11-04T19:17:30+09:00')
        self.assertEqual(c['bosses'][0]['schedule']['minutes'],660)

    def test_agro_both_daily_boundaries_midnight_and_notification_deduplication(self):
        c=defaults();upgrade_boss_catalog(c)
        row=next(r for r in c['bosses'] if r['id']=='spirit-king-argo')
        for hour,minute,expected in [(10,29,'10:30'),(10,30,'22:30'),(22,29,'22:30'),(22,30,'10:30'),(23,59,'10:30')]:
            now=dt.datetime(2026,11,4,hour,minute,tzinfo=JST)
            nxt=next_occurrence(row['schedule'],now).astimezone(JST)
            self.assertEqual(nxt.strftime('%H:%M'),expected)
            self.assertGreater(nxt,now)
        tracker=Tracker(c,{'bells':{row['id']:True},'leads':{row['id']:0}})
        for hour in (10,22):
            at=dt.datetime(2026,11,4,hour,30,tzinfo=JST)
            tracker.tick(at-dt.timedelta(seconds=1))
            self.assertEqual(tracker.tick(at)[1],['精霊王アグロⅡ'])
            self.assertEqual(tracker.tick(at)[1],[])
        with self.assertRaises(ValueError):validate_schedule(dict(row['schedule'],times=['25:30']))

    def test_artifact_migration_is_once_and_keeps_notification_choices(self):
        original={'events':[{'id':'artifact','name_en':'Artifact Siege','name_ja':'自分の名前','alert_enabled':False,'sound_enabled':False}],
                  'event_schema':2,'schedule_update_134':True}
        c=migrate_config(original);e=c['events'][0]
        self.assertEqual(e['weekdays'],[3,5]);self.assertEqual(e['times'],['21:00'])
        self.assertFalse(e['alert_enabled']);self.assertFalse(e['sound_enabled'])
        for day in range(7):
            at=dt.datetime(2026,11,2+day,21,tzinfo=JST)
            check=dict(e,alert_enabled=True)
            self.assertEqual(bool(due_notifications(check,at-dt.timedelta(seconds=1),at)),day in (3,5))
        e['weekdays']=[6];self.assertEqual(migrate_config(c)['events'][0]['weekdays'],[6])

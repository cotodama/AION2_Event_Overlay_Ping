import copy
import datetime as dt
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from boss_groups import boss_display_items,members,next_boss_occurrence
from boss_catalog import upgrade_boss_catalog
from tracker_model import defaults,Tracker,UTC,validate_schedule

class BossTests(unittest.TestCase):
    def test_group_keeps_distinct_saved_schedules(self):
        catalog=defaults(); before=copy.deepcopy(catalog)
        grouped=boss_display_items(catalog['bosses'])
        self.assertEqual(len(grouped),1); self.assertEqual(grouped[0]['name'],'NM ガルトゥア')
        self.assertEqual(catalog,before)
        self.assertEqual([r['id'] for r in members(grouped[0])],['gartua-elyos','gartua-asmo'])

    def test_added_once_deleted_not_reappearing(self):
        c=defaults(); self.assertTrue(upgrade_boss_catalog(c))
        self.assertEqual(len(c['bosses']),9)
        c['bosses']=[]; self.assertFalse(upgrade_boss_catalog(c)); self.assertEqual(c['bosses'],[])

    def test_multiple_weekdays_exact_boundary_and_single_notification(self):
        c=defaults(); upgrade_boss_catalog(c); row=next(r for r in c['bosses'] if r['id']=='executor-argo')
        t=Tracker(c,{'bells':{row['id']:True},'leads':{row['id']:0}})
        before=dt.datetime(2026,10,12,12,29,59,tzinfo=UTC)
        t.tick(before); self.assertEqual(t.tick(before+dt.timedelta(seconds=1))[1],['執行者アグロ'])
        self.assertEqual(t.tick(before+dt.timedelta(seconds=2))[1],[])
        nxt=next_boss_occurrence(row,before+dt.timedelta(seconds=1))[0]
        self.assertEqual((nxt.weekday(),nxt.hour,nxt.minute),(3,12,30))

    def test_empty_and_invalid_weekday_list_rejected(self):
        for days in ([],[0,7]):
            with self.assertRaises(ValueError): validate_schedule({'kind':'weekly','weekdays':days,'time':'21:30','utc_offset':9})

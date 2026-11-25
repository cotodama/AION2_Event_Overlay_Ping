import copy,datetime as dt,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from boss_catalog import upgrade_boss_catalog
from tracker_model import defaults,next_occurrence,Tracker
from schedule_table_model import JST,GARTUA_NOVEMBER_DATES

class GartuaCycleTests(unittest.TestCase):
    def test_supplied_times_match_11h_and_continue_after_reference_week(self):
        c=defaults();upgrade_boss_catalog(c);s=c['bosses'][0]['schedule']
        previous=dt.datetime(2026,11,25,20,29,59,tzinfo=JST)
        supplied=[dt.datetime.combine(dt.date.fromisoformat(day),dt.time.fromisoformat(t),JST)
            for day,times in GARTUA_NOVEMBER_DATES.items() for t in times]
        for expected in supplied:
            actual=next_occurrence(s,previous);self.assertEqual(actual,expected);previous=actual
        self.assertEqual(next_occurrence(s,previous),dt.datetime(2026,12,3,4,30,tzinfo=JST))
        after=dt.datetime(2027,1,1,tzinfo=JST);nxt=next_occurrence(s,after)
        self.assertGreater(nxt,after);self.assertLessEqual(nxt-after,dt.timedelta(hours=11))

    def test_migration_from_139_preserves_other_bosses_and_manual_edit_after_restart(self):
        c=defaults();upgrade_boss_catalog(c);c['named_catalog_version']=6
        c['bosses'][0]['display_name']='私のガルトゥア'
        original=copy.deepcopy(c)
        self.assertTrue(upgrade_boss_catalog(c));self.assertEqual(c['named_catalog_version'],7)
        for before,after in zip(original['bosses'],c['bosses']):
            if not after['id'].startswith('gartua-'):self.assertEqual(before,after)
            else:self.assertEqual(after.get('display_name'),before.get('display_name'))
        c['bosses'][0]['schedule']['anchor']='2026-12-02T21:45:30+09:00';c['bosses'][0]['schedule']['minutes']=690
        edited=copy.deepcopy(c);self.assertFalse(upgrade_boss_catalog(c));self.assertEqual(c,edited)

    def test_interval_notifications_continue_once_after_end_of_reference_list(self):
        c=defaults();upgrade_boss_catalog(c);row=c['bosses'][0]
        tracker=Tracker(c,{'bells':{row['id']:True},'leads':{row['id']:5}})
        due=dt.datetime(2026,12,3,4,25,tzinfo=JST)
        tracker.tick(due-dt.timedelta(seconds=1));self.assertEqual(tracker.tick(due)[1],[row['name']])
        self.assertEqual(tracker.tick(due)[1],[])

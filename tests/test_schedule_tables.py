import copy,datetime as dt,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from schedule_table_model import JST,table_schedule,GARTUA_NOVEMBER_DATES
from tracker_model import defaults,validate_schedule,next_occurrence,Tracker
from boss_catalog import upgrade_boss_catalog
from boss_groups import boss_display_items,next_boss_occurrence

class ScheduleTableTests(unittest.TestCase):
    def test_weekdays_independent_multi_times_and_week_rollover(self):
        s=table_schedule('weekly_times',{'0':['10:00','21:00'],'1':['08:00','19:00'],
            '2':['06:00','17:00'],'3':['07:00','18:00'],'4':['05:00','16:00'],
            '5':['03:00','14:00'],'6':['01:00','12:00','23:00']})
        for day,values in s['table'].items():
            for value in values:
                at=dt.datetime.combine(dt.date(2026,11,9)+dt.timedelta(days=int(day)),dt.time.fromisoformat(value),JST)
                self.assertEqual(next_occurrence(s,at-dt.timedelta(seconds=1)),at)
                self.assertGreater(next_occurrence(s,at),at)
        empty=table_schedule('weekly_times',{'0':['00:00:30'],'6':[]})
        at=dt.datetime(2026,11,9,0,0,30,tzinfo=JST)
        self.assertEqual(next_occurrence(empty,at),at+dt.timedelta(days=7))

    def test_all_16_supplied_dates_and_no_repeat_after_last(self):
        s=table_schedule('dates',GARTUA_NOVEMBER_DATES)
        for day,values in GARTUA_NOVEMBER_DATES.items():
            for value in values:
                at=dt.datetime.combine(dt.date.fromisoformat(day),dt.time.fromisoformat(value),JST)
                self.assertEqual(next_occurrence(s,at-dt.timedelta(seconds=1)),at)
        end=dt.datetime(2026,12,2,17,30,tzinfo=JST)
        self.assertIsNone(next_occurrence(s,end));self.assertIsNone(next_occurrence(s,end+dt.timedelta(days=7)))

    def test_two_different_wednesdays_are_not_merged(self):
        s=table_schedule('dates',GARTUA_NOVEMBER_DATES)
        for month,date,expected in [(11,25,'20:30'),(12,2,'06:30')]:
            at=dt.datetime(2026,month,date,0,tzinfo=JST)
            self.assertEqual(next_occurrence(s,at).strftime('%H:%M'),expected)

    def test_notification_lead_across_midnight_and_dedup_after_restart(self):
        c=defaults();upgrade_boss_catalog(c)
        row=c['bosses'][0];row['schedule']=table_schedule('weekly_times',{'0':['00:03'],'1':['01:00','12:00','23:00']})
        state={'bells':{row['id']:True},'leads':{row['id']:5}}
        tracker=Tracker(c,state)
        due=dt.datetime(2026,11,8,23,58,tzinfo=JST)
        tracker.tick(due-dt.timedelta(seconds=1));self.assertEqual(tracker.tick(due)[1],[row['name']])
        again=Tracker(c,json.loads(json.dumps(state)));again.tick(due-dt.timedelta(seconds=1))
        self.assertEqual(again.tick(due)[1],[])

    def test_each_of_three_same_day_times_notifies_once(self):
        c=defaults();upgrade_boss_catalog(c);row=c['bosses'][0]
        row['schedule']=table_schedule('dates',GARTUA_NOVEMBER_DATES)
        state={'bells':{row['id']:True},'leads':{row['id']:0}};tracker=Tracker(c,state)
        for hour in (1,12,23):
            at=dt.datetime(2026,11,29,hour,30,tzinfo=JST)
            tracker.tick(at-dt.timedelta(seconds=1));self.assertEqual(tracker.tick(at)[1],[row['name']])
            self.assertEqual(tracker.tick(at)[1],[])

    def test_invalid_and_empty_tables_rejected(self):
        for kind,table in [('weekly_times',{'7':['01:00']}),('dates',{'2026-02-30':['01:00']}),
            ('dates',{'2026-11-12':['24:00']}),('dates',{'2026-11-12':['07:60']}),
            ('dates',{'2026-11-12':['07:00+09:00']}),('weekly_times',{'1':[]}),('weekly_times',{'1':'07:00'})]:
            with self.subTest(table=table),self.assertRaises(ValueError):table_schedule(kind,table)

    def test_normalization_sorts_deduplicates_without_mutation(self):
        original={'6':['23:00','01:00:00','23:00'],'0':[]};before=copy.deepcopy(original)
        s=table_schedule('weekly_times',original);self.assertEqual(s['table'],{'6':['01:00','23:00']})
        self.assertEqual(original,before);validate_schedule(s)

    def test_upgrade_only_changes_existing_gartua_once_and_keeps_ragta(self):
        c=defaults();upgrade_boss_catalog(c);c['named_catalog_version']=4
        c['bosses']=[r for r in c['bosses'] if r['id']!='gartua-asmo']
        ragta=next(r for r in c['bosses'] if r['id']=='ragta-elyos')
        ragta['schedule']=table_schedule('weekly_times',{'2':['18:15'],'3':['05:15','16:15']})
        before=copy.deepcopy(ragta);ids=[r['id'] for r in c['bosses']]
        upgrade_boss_catalog(c);self.assertEqual(ragta,before);self.assertEqual([r['id'] for r in c['bosses']],ids)
        g=c['bosses'][0];g['schedule']=table_schedule('weekly_times',{'6':['19:30']})
        expected=copy.deepcopy(c);self.assertFalse(upgrade_boss_catalog(c));self.assertEqual(c,expected)

    def test_grouped_factions_keep_distinct_times_and_choose_earliest(self):
        c=defaults();upgrade_boss_catalog(c)
        for row in c['bosses']:
            if row['id'].startswith('gartua-'):
                row['schedule']=table_schedule('weekly_times',{'3':['08:00' if row['id'].endswith('elyos') else '09:00']})
        group=boss_display_items(c['bosses'])[0];now=dt.datetime(2026,11,12,7,tzinfo=JST)
        self.assertEqual(next_boss_occurrence(group,now)[0].astimezone(JST).hour,8)
        self.assertEqual(next_boss_occurrence(group,now+dt.timedelta(hours=1))[0].astimezone(JST).hour,9)

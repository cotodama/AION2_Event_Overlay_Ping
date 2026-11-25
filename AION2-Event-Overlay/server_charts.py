"""Native charts based on gaming.tools' public JSON and published visual semantics.

No embedded browser or HTML/JS is fetched at runtime. Missing samples stay missing.
Reference checked 2026-11-26: blue Elyos, purple Asmodian; load != player count.
"""
import datetime as dt
import math
import tkinter as tk
from server_data import filtered_servers, status_label, balance_fraction, REGIONS

PAIRING_SOURCE='https://steamcommunity.com/ogg/3393110/announcements/detail/675136971036689542'
# Published November 11 Abyss matching (includes same-faction pairs).
MATCHES={
 'EU':[['Triniel','Kaisinel'],['Lumiel','Zikel'],['Siel','Vaizel'],['Israphel','Marchutan'],['Ludra','Bakarma'],['Nezekan','Zemurru'],['Baba','Azphel'],['Ereshkigal','Phernos'],['Nania','Beritra'],['Hadala','Kromede'],['Ulgorn','Odar'],['Nemon','Fafnir'],['Tiamat','Quai'],['Atiel','Agnita'],['Munin','Ariel'],['Yustiel','Indnath'],['Fregion','Tassin'],['Tahavatha','Meslamtaeda'],['Hithanya','Luteros'],['Kasaka','Kochi'],['Gauss','Nathara'],['Ishtar','Daminu'],['Tsenka','Lamuatan']],
 'NAE':[['Israphel','Siel'],['Zikel','Nezekan'],['Triniel','Azphel'],['Lumiel','Yustiel'],['Ereshkigal','Kaisinel'],['Ariel','Beritra'],['Vaizel','Hithanya'],['Marchutan','Nemon'],['Meslamtaeda','Fregion']],
 'NAW':[['Siel','Israphel'],['Lumiel','Zikel'],['Vaizel','Marchutan'],['Triniel','Yustiel'],['Nezekan','Kaisinel']],
 'LA':[['Ariel','Zikel'],['Israphel','Siel'],['Marchutan','Lumiel'],['Triniel','Kaisinel'],['Vaizel','Azphel'],['Nezekan','Yustiel']],
 'AS':[['Siel','Ariel'],['Israphel','Lumiel'],['Nezekan','Nemon'],['Zikel','Marchutan'],['Vaizel','Ereshkigal'],['Kaisinel','Hithanya'],['Yustiel','Triniel'],['Fregion','Nania'],['Meslamtaeda','Azphel'],['Beritra','Hadala']]}
BLUE='#1898f3';PURPLE='#af57e5';MUTED='#a4b9bd'
JST=dt.timezone(dt.timedelta(hours=9))

def valid_number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0

def live_load(server):
    if not server or server.get('state','live')!='live' or not server.get('isRunning') or server.get('inMaintenance'):return None
    value=server.get('load');return value if valid_number(value) else None

def series(server):
    return sorted([dict(t=p['t'],value=p.get('value') if valid_number(p.get('value')) else None)
                   for p in (server or {}).get('spark',[]) if isinstance(p,dict) and valid_number(p.get('t'))],key=lambda p:p['t'])

def paired_series(first,second):
    a={p['t']:p['value'] for p in series(first)};b={p['t']:p['value'] for p in series(second)}
    return [dict(t=t,first=a.get(t),second=b.get(t)) for t in sorted(a.keys()|b.keys())]

def aggregate(servers):
    if not servers:return None
    loads=[live_load(s) for s in servers];points={}
    for s in servers:
        for p in series(s):points.setdefault(p['t'],[]).append(p['value'])
    return dict(load=sum(loads)/len(loads) if all(x is not None for x in loads) else None,
                isRunning=True,state='live',spark=[dict(t=t,value=sum(v)/len(v) if len(v)==len(servers) and all(x is not None for x in v) else None) for t,v in sorted(points.items())])

def peak_window(points,region_points):
    """Highest four consecutive hourly regional samples; paired values at same hours."""
    best=None
    for i in range(max(0,len(region_points)-3)):
        block=region_points[i:i+4]
        if any(p['value'] is None for p in block) or block[-1]['t']-block[0]['t']!=3*3600000:continue
        score=sum(p['value'] for p in block)
        if best is None or score>best[0]:best=(score,block)
    if best is None:return None
    times={p['t'] for p in best[1]};pairs=[p for p in points if p['t'] in times and p['first'] is not None and p['second'] is not None]
    if not pairs:return None
    return (sum(p['first'] for p in pairs)/len(pairs),sum(p['second'] for p in pairs)/len(pairs),best[1][0]['t'])

def faction_color(server):return PURPLE if (server or {}).get('faction')=='Asmodian' else BLUE
def faction_name(server):return {'Elyos':'天族','Asmodian':'魔族'}.get((server or {}).get('faction'),'未確認')
def pct(value):return '未確認' if value is None else f'{value:.0%}'
def clock(stamp):return dt.datetime.fromtimestamp(stamp/1000,JST).strftime('%m/%d %H:%M')

class ServerChartsMixin:
    def chart_canvas(self,height,paint):
        colors=self.theme_colors();c=tk.Canvas(self.list_area.body,width=max(270,self.overlay_width-35),height=height,bg=colors['card'],highlightthickness=0)
        c.pack(fill='x',pady=3)
        def redraw(event=None):
            c.delete('all');paint(c,max(260,c.winfo_width()))
        c.bind('<Configure>',redraw);redraw();self.list_area.install_wheel(c);return c

    def chart_text(self,c,x,y,text,anchor='w',color=None,bold=False,size=9):
        return c.create_text(x,y,text=text,anchor=anchor,fill=color or self.theme_colors()['text'],font=self.ui(size,'bold' if bold else 'normal'))

    def load_bar(self,c,x,y,width,load,server=None):
        c.create_rectangle(x,y,x+width,y+9,fill='#293848',outline='')
        if load is None:return
        busy=(server or {}).get('busyAt');full=self.db_snapshot.get('fullAt')
        color='#ef4444' if full is not None and load>=full else '#f59e0b' if busy is not None and load>=busy else '#10b981'
        c.create_rectangle(x,y,x+width*min(1,load),y+9,fill=color,outline='')

    def draw_spark(self,canvas,points,x,y,width=145,height=25,capacity=None):
        # The current schema contains normalized load, not population counts.
        values=[p.get('value') for p in points if valid_number(p.get('value'))]
        normalized=capacity is None
        scale=1 if normalized else max([capacity or 0]+values+[1])
        step=width/max(1,len(points))
        canvas.create_line(x,y+height,x+width,y+height,fill='#465568')
        for i,p in enumerate(points):
            v=p.get('value');left=x+i*step
            if not valid_number(v):
                canvas.create_rectangle(left,y+height-2,left+max(.6,step-1),y+height,fill='#64748b',outline='');continue
            h=max(1,min(1,v/scale)*height)
            color='#10b981' if v/scale<.7 else '#f59e0b' if v/scale<.9 else '#ef4444'
            canvas.create_rectangle(left,y+height-h,left+max(.6,step-1),y+height,fill=color,outline='')
        if height>=40:
            self.chart_text(canvas,x,y-7,'24時間 · 混雑度 0–100%',size=8,color=MUTED)
            if points:
                self.chart_text(canvas,x,y+height+12,clock(points[0]['t']),size=8,color=MUTED)
                self.chart_text(canvas,x+width,y+height+12,clock(points[-1]['t']),anchor='e',size=8,color=MUTED)
        def hover(event):
            canvas.delete('hover')
            if not points or not x<=event.x<=x+width:return
            p=points[min(len(points)-1,int((event.x-x)/width*len(points)))];value=p.get('value')
            label=clock(p['t'])+' JST · '+(pct(value) if normalized else str(value) if value is not None else '未確認')
            canvas.create_rectangle(x,y-21,x+width,y-1,fill='#101827',outline='',tags='hover')
            canvas.create_text(x+4,y-11,text=label,fill='white',anchor='w',font=self.ui(8),tags='hover')
        canvas.bind('<Motion>',hover);canvas.bind('<Leave>',lambda e:canvas.delete('hover'))

    def render_db(self):
        if self.active_tab not in ('status','balance') or not hasattr(self,'db_info'):return
        self.list_area.clear()
        if not self.db_snapshot:self.update_db_request_label();return
        stamps=[r.get('lastUpdated') for r in self.db_snapshot['regions'] if r.get('lastUpdated')]
        stamp=min(stamps) if stamps else self.db_snapshot.get('generatedAt')
        try:stamp=dt.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(JST).strftime('%m/%d %H:%M:%S JST')
        except (ValueError,AttributeError):stamp='未確認'
        self._db_stamp=stamp
        self.update_db_request_label()
        if self.active_tab=='balance':self.render_balance();return
        self.render_steam_history()
        for region in self.db_snapshot['regions']:
            if self.db_region!='all' and region['code']!=self.db_region:continue
            def region_chart(c,w,r=region):
                self.chart_text(c,10,17,dict(REGIONS).get(r['code'],r['code'])+' · '+pct(r.get('load')),bold=True)
                self.chart_text(c,10,39,f"{r.get('onlineCount',0)} / {len(r['servers'])} オンライン",size=8,color=MUTED)
                self.draw_spark(c,series(r),10,70,w-20,48,None)
            self.chart_canvas(142,region_chart)
        state={'すべて':'all','オンライン':'online','問題あり':'issues'}[self.db_filter.get()]
        worlds=filtered_servers(self.db_snapshot,self.db_region,self.search_var.get(),state)
        def key(s):
            value=status_label(s) if self.sort_field=='status' else s.get(self.sort_field)
            return (value is None,value if value is not None else '')
        worlds.sort(key=key,reverse=self.sort_desc)
        self.label(self.list_area.body,f'{len(worlds)} サーバー · 人口＝混雑度（人数ではありません）',anchor='w',wraplength=max(270,self.overlay_width-40)).pack(fill='x',pady=4)
        if self.table_var.get():self.render_status_table(worlds)
        else:
            for s in worlds:
                def paint(c,w,s=s):
                    self.draw_name(c,s['name'],10,17,s['creationBlocked'])
                    self.chart_text(c,w-10,17,status_label(s),anchor='e',color='#10b981' if live_load(s) is not None else '#f59e0b')
                    self.chart_text(c,10,43,f"{faction_name(s)} · {s['region']} · 混雑度 {pct(live_load(s))}",color=faction_color(s))
                    self.load_bar(c,10,57,w-20,live_load(s),s)
                    self.draw_spark(c,series(s),10,94,w-20,64,None)
                self.chart_canvas(182,paint)
        if not worlds:self.label(self.list_area.body,'該当するサーバーがありません').pack(pady=20)
        self.apply_extension_surface()

    def render_steam_history(self):
        history=self.db_snapshot.get('steamHistory') or {};hourly=history.get('hourly') or {}
        values=hourly.get('values',[]);start=hourly.get('start')
        if not values or start is None:return
        controls=tk.Frame(self.list_area.body,bg=self.theme_colors()['root']);controls.pack(fill='x',pady=4)
        for hours,label in ((24,'24時間'),(168,'7日間'),(720,'30日間')):
            def select(n=hours):self._steam_hours=n;self.render_db()
            self.button(controls,label,select,padx=5).pack(side='left',padx=2)
        count=getattr(self,'_steam_hours',24);offset=max(0,len(values)-count)
        points=[dict(t=start+i*3600000,value=v) for i,v in enumerate(values) if i>=offset]
        def paint(c,w):
            players=self.db_snapshot.get('steamPlayers');self.chart_text(c,10,17,'Steamプレイヤー '+(f'{players:,}' if valid_number(players) else '未確認'),bold=True,color='#eab308')
            self.chart_text(c,10,38,'全地域合計 · 1時間平均（サーバー別人数ではありません）',size=8,color=MUTED)
            top=64;bottom=146;peak=max([p['value'] for p in points if valid_number(p['value'])]+[1]);last=None
            self.chart_text(c,w-10,52,f'上限 {peak:,}',anchor='e',size=8,color=MUTED)
            for i,p in enumerate(points):
                x=10+(w-20)*i/max(1,len(points)-1);v=p['value']
                if not valid_number(v):last=None;continue
                y=bottom-v/peak*(bottom-top)
                if last:c.create_line(*last,x,y,fill='#eab308',width=2)
                last=(x,y)
            c.create_line(10,bottom,w-10,bottom,fill='#465568')
            self.chart_text(c,10,162,clock(points[0]['t']),size=8,color=MUTED)
            self.chart_text(c,w-10,162,clock(points[-1]['t']),anchor='e',size=8,color=MUTED)
            def hover(event):
                c.delete('hover')
                if not 10<=event.x<=w-10:return
                p=points[min(len(points)-1,round((event.x-10)/(w-20)*(len(points)-1)))];v=p['value']
                c.create_rectangle(8,176,w-8,196,fill='#101827',outline='',tags='hover')
                c.create_text(12,186,text=clock(p['t'])+' JST · '+(f'{v:,}' if valid_number(v) else '未確認'),fill='white',anchor='w',font=self.ui(8),tags='hover')
            c.bind('<Motion>',hover);c.bind('<Leave>',lambda e:c.delete('hover'))
        self.chart_canvas(200,paint)

    def update_db_request_label(self):
        import time
        button=getattr(self,'db_refresh_button',None)
        if button is not None and button.winfo_exists():button.configure(state='disabled' if self.fetch_busy else 'normal')
        if self.active_tab not in ('status','balance') or not hasattr(self,'db_info'):return
        if not self.db_snapshot:
            from ping_feature import PingFeatureMixin
            return PingFeatureMixin.update_db_request_label(self)
        remaining=max(0,math.ceil(self.next_fetch-time.monotonic()));minutes,seconds=divmod(remaining,60)
        state='取得中…' if self.fetch_busy else ('取得失敗・前回値を表示' if self.fetch_error else '次回 '+f'{minutes:02}:{seconds:02}')
        self.db_info.configure(text='データ時刻 '+getattr(self,'_db_stamp','未確認')+' · '+state+'（15分間隔）',fg='#f59e0b' if self.fetch_error else MUTED)

    def render_status_table(self,worlds):
        self.label(self.list_area.body,'状態 / サーバー / 種族 / 地域 / 混雑度 / 過去24時間',anchor='w').pack(fill='x')
        for s in worlds:
            def paint(c,w,s=s):
                self.chart_text(c,10,16,s['name'],color=faction_color(s),bold=True)
                self.chart_text(c,w-10,16,pct(live_load(s)),anchor='e')
                self.chart_text(c,10,38,f"{status_label(s)} · {faction_name(s)} · {s['region']}"+(' · 作成制限' if s['creationBlocked'] else ''),size=8,color=MUTED)
                self.load_bar(c,10,49,w-20,live_load(s),s)
                self.draw_spark(c,series(s),10,76,w-20,40,None)
            self.chart_canvas(140,paint)

    def ratio_bar(self,c,a,b,x,y,width,first=None,second=None):
        fraction=balance_fraction(a,b);ca=faction_color(first);cb=faction_color(second)
        self.chart_text(c,x,y,pct(fraction),color=ca,size=8)
        self.chart_text(c,x+width,y,pct(1-fraction if fraction is not None else None),anchor='e',color=cb,size=8)
        c.create_rectangle(x,y+10,x+width,y+22,fill='#293848',outline='')
        if fraction is not None:
            c.create_rectangle(x,y+10,x+width*fraction,y+22,fill=ca,outline='')
            c.create_rectangle(x+width*fraction,y+10,x+width,y+22,fill=cb,outline='')
        c.create_line(x+width/2,y+8,x+width/2,y+24,fill='#dce5ec')

    def balance_card(self,title,first,second,region):
        points=paired_series(first,second);peak=peak_window(points,series(region))
        def paint(c,w):
            self.chart_text(c,10,17,title,bold=True)
            left=(first or {}).get('name','天族');right=(second or {}).get('name','魔族')
            self.chart_text(c,10,40,left+' · '+faction_name(first)+' '+pct(live_load(first)),color=faction_color(first),size=8)
            self.chart_text(c,w-10,40,right+' · '+faction_name(second)+' '+pct(live_load(second)),anchor='e',color=faction_color(second),size=8)
            self.ratio_bar(c,live_load(first),live_load(second),10,63,w-20,first,second)
            if peak:
                a,b,t=peak;start=dt.datetime.fromtimestamp(t/1000,JST)
                self.chart_text(c,10,106,'ピークタイム '+start.strftime('%H:%M')+'–'+(start+dt.timedelta(hours=4)).strftime('%H:%M')+' JST',size=8,color=MUTED)
                self.ratio_bar(c,a,b,10,127,w-20,first,second)
            else:self.chart_text(c,10,106,'ピークタイム: 未確認',size=8,color=MUTED)
            y=186;step=(w-20)/max(1,len(points));c.create_line(10,y,w-10,y,fill='#64748b')
            for i,p in enumerate(points):
                f=balance_fraction(p['first'],p['second']);h=1 if f is None else max(1,min(1,abs(f-.5)/.25)*24)
                top=y-h if f is not None and f>=.5 else y
                color='#64748b' if f is None else faction_color(first if f>=.5 else second)
                c.create_rectangle(10+i*step,top,10+i*step+max(.6,step-1),top+h,fill=color,outline='')
            self.chart_text(c,10,162,'24時間の推移 · 左が優勢↑ / 右が優勢↓',size=8,color=MUTED)
            if points:
                self.chart_text(c,10,224,clock(points[0]['t']),size=8,color=MUTED)
                self.chart_text(c,w-10,224,clock(points[-1]['t']),anchor='e',size=8,color=MUTED)
            def hover(event):
                c.delete('hover')
                if not points or event.y<165 or not 10<=event.x<=w-10:return
                p=points[min(len(points)-1,int((event.x-10)/(w-20)*len(points)))];f=balance_fraction(p['first'],p['second'])
                text=clock(p['t'])+' JST · '+pct(f)+' / '+pct(None if f is None else 1-f)
                c.create_rectangle(8,235,w-8,254,fill='#101827',outline='',tags='hover')
                c.create_text(12,244,text=text,anchor='w',fill='white',font=self.ui(8),tags='hover')
            c.bind('<Motion>',hover);c.bind('<Leave>',lambda e:c.delete('hover'))
        self.chart_canvas(258,paint)

    def render_balance(self):
        self.label(self.list_area.body,'現在の混雑度比率 · ピークタイム · 過去24時間の推移',anchor='w',wraplength=max(260,self.overlay_width-40)).pack(fill='x',pady=5)
        for region in self.db_snapshot['regions']:
            if self.db_region!='all' and region['code']!=self.db_region:continue
            worlds=region['servers'];search=self.search_var.get().casefold();used=set()
            if not search:
                a=aggregate([s for s in worlds if s['faction']=='Elyos']);b=aggregate([s for s in worlds if s['faction']=='Asmodian'])
                if a:a.update(name='天族',faction='Elyos')
                if b:b.update(name='魔族',faction='Asmodian')
                self.balance_card(dict(REGIONS).get(region['code'],region['code'])+' · 地域全体',a,b,region)
            for an,bn in MATCHES.get(region['code'],[]):
                a=next((s for s in worlds if s['name']==an),None);b=next((s for s in worlds if s['name']==bn),None)
                used.update([an,bn])
                if not(a or b) or search and search not in (an+' '+bn).casefold():continue
                # Keep source's left/right faction convention without assuming opposite factions.
                if a and b and a['faction']=='Asmodian' and b['faction']=='Elyos':a,b=b,a
                self.balance_card(an+' / '+bn,a,b,region)
            for s in worlds:
                if s['name'] not in used and (not search or search in s['name'].casefold()):
                    self.label(self.list_area.body,s['name']+' · '+faction_name(s)+' · 混雑度 '+pct(live_load(s))+' · 公開ペア未確認',anchor='w').pack(fill='x',pady=5)
        self.label(self.list_area.body,'同じ種族同士のペアもあります。人数は未公開です。欠測は灰色で表示します。',wraplength=max(260,self.overlay_width-40),justify='left').pack(fill='x',pady=8)
        self.button(self.list_area.body,'アビスの組み合わせ（2026/11/11）',lambda:self.open_tracker_link(PAIRING_SOURCE)).pack(pady=5)
        self.apply_extension_surface()

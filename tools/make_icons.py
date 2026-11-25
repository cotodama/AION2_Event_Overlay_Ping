from pathlib import Path
from PIL import Image,ImageDraw
folder=Path(__file__).resolve().parents[1]/'assets/icons';folder.mkdir(parents=True,exist_ok=True)
names=('bell','bell-off','settings','timer','move','play','pause','plus','close','boss','signal')
for name in names:
    image=Image.new('RGBA',(24,24));d=ImageDraw.Draw(image);color='#e7f2f5';line=lambda pts:d.line(pts,fill=color,width=2)
    if name.startswith('bell'):
        d.arc((6,4,18,19),180,360,fill=color,width=2);line([(6,10),(6,16),(4,18),(20,18),(18,16),(18,10)])
        d.arc((9,17,15,23),0,180,fill=color,width=2)
        if name=='bell-off':line([(3,3),(21,21)])
    elif name=='settings':
        d.ellipse((5,5,19,19),outline=color,width=2);d.ellipse((9,9,15,15),outline=color,width=2)
        for x,y in [(12,1),(12,21),(1,12),(21,12)]:d.rectangle((x-1,y-1,x+1,y+1),fill=color)
    elif name=='timer':d.ellipse((4,5,20,21),outline=color,width=2);line([(9,2),(15,2)]);line([(12,7),(12,13),(16,13)])
    elif name=='move':
        line([(12,2),(12,22)]);line([(2,12),(22,12)])
        for pts in [[(8,6),(12,2),(16,6)],[(8,18),(12,22),(16,18)],[(6,8),(2,12),(6,16)],[(18,8),(22,12),(18,16)]]:line(pts)
    elif name=='play':d.polygon([(7,4),(20,12),(7,20)],fill=color)
    elif name=='pause':d.rectangle((6,4,9,20),fill=color);d.rectangle((15,4,18,20),fill=color)
    elif name=='plus':line([(12,4),(12,20)]);line([(4,12),(20,12)])
    elif name=='close':line([(6,6),(18,18)]);line([(18,6),(6,18)])
    elif name=='boss':
        d.polygon([(3,3),(8,7),(16,7),(21,3),(19,17),(12,22),(5,17)],outline=color)
        line([(7,12),(10,13)]);line([(14,13),(17,12)]);line([(9,17),(15,17)])
    elif name=='signal':
        for x,h in [(3,4),(8,8),(13,12),(18,17)]:d.rectangle((x,21-h,x+2,21),fill=color)
    image.save(folder/(name+'.png'))

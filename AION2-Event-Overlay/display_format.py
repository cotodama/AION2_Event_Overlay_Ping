"""Readable durations rounded up to the next minute for upcoming events."""
import math

def remaining_text(seconds):
    minutes=max(0,math.ceil(seconds/60))
    hours,minutes=divmod(minutes,60)
    return f'{hours}時間{minutes}分' if hours else f'{minutes}分'


def precise_remaining(seconds):
    seconds=max(0,int(seconds));hours,seconds=divmod(seconds,3600);mins,secs=divmod(seconds,60)
    return (f'{hours}時間' if hours else '')+f'{mins}分{secs:02d}秒'

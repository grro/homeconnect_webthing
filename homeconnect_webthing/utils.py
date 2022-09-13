from datetime import datetime

def print_duration(time: int):
    if time > 60 * 60:
        return str(round(time/(60*60), 1)) + " hour"
    elif time > 60:
        return str(round(time/60, 1)) + " min"
    else:
        return str(time) + " sec"



class DailyRequestCounter:

    def __init__(self):
        self.count = 0
        self.day = datetime.now().strftime('%Y-%m-%d')

    def inc(self):
        current_day = datetime.now().strftime('%Y-%m-%d')
        if current_day != self.day:
            self.day = current_day
            self.count = 1
        else:
            self.count += 1




def print_duration(time: int):
    if time > 60 * 60:
        return str(round(time/(60*60), 1)) + " hour"
    elif time > 60:
        return str(round(time/60, 1)) + " min"
    else:
        return str(time) + " sec"


def is_success(status_code: int) -> bool:
    return status_code >= 200 and status_code <= 299

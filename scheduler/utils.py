def time_to_minutes(time_str: str) -> int:
    hours, minutes = map(int, time_str.split(":"))
    return hours * 60 + minutes


def minutes_to_time(minutes: int) -> str:
    day_offset = minutes // (24 * 60)
    clock = minutes % (24 * 60)
    hours = clock // 60
    mins = clock % 60
    label = f"{hours:02d}:{mins:02d}"
    if day_offset:
        label += f" (+{day_offset}d)"
    return label
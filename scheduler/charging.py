from scheduler.models import World


def full_charge_minutes(world: World) -> int:
    """Assignment rule: every charge fills the battery (25 min)."""
    return world.charging_time_minutes


# --- Future: partial top-up (not used for assignment submission) ---
#
# def charge_minutes_for_distance(distance_km, world): ...

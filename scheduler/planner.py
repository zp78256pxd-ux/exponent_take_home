def _leg_distance(
    distances: list[int],
    from_charge_idx: int,
    to_charge_idx: int,
) -> int:
    """
    Distance between charge points along the corridor.

    from_charge_idx=-1 means origin (BLR); to_charge_idx=len(stations)
    means destination (KOC) when there are n charging stations.
    """
    start = from_charge_idx + 1
    end = to_charge_idx + 1
    return sum(distances[start:end])


def _is_valid_plan(
    stations: list[str],
    distances: list[int],
    plan: list[str],
    battery_range: int,
) -> bool:
    if not plan:
        return False

    charge_points = [-1]
    for station in plan:
        charge_points.append(stations.index(station))
    charge_points.append(len(stations))

    for i in range(len(charge_points) - 1):
        leg = _leg_distance(
            distances,
            charge_points[i],
            charge_points[i + 1],
        )
        if leg > battery_range:
            return False

    return True


def generate_valid_plans(
    stations: list[str],
    distances: list[int],
    battery_range: int,
) -> list[list[str]]:
    """
    Find all valid charging plans via backtracking DFS.

    Walks corridor segments in order. After each segment, optionally
    charge at that station (reset range) or continue. Prunes when range
    would be exceeded.

    Example:
        stations = ["A", "B", "C", "D"]
        distances = [100, 120, 100, 120, 100]  # BLR→A→B→C→D→KOC
    """
    valid_plans: list[list[str]] = []

    def dfs(
        seg_idx: int,
        dist_since_charge: int,
        plan: list[str],
    ) -> None:
        if seg_idx == len(stations):
            final_leg = distances[seg_idx]
            if (
                plan
                and dist_since_charge + final_leg <= battery_range
                and _is_valid_plan(
                    stations,
                    distances,
                    plan,
                    battery_range,
                )
            ):
                valid_plans.append(list(plan))
            return

        new_dist = dist_since_charge + distances[seg_idx]
        if new_dist > battery_range:
            return

        station = stations[seg_idx]

        dfs(seg_idx + 1, 0, plan + [station])

        dfs(seg_idx + 1, new_dist, plan)

    dfs(0, 0, [])
    return valid_plans


# ---------------------------------------------------------------------------
# Brute force (commented) — try every station subset, then filter by range
# ---------------------------------------------------------------------------
#
# from itertools import combinations
#
#
# def generate_valid_plans_brute_force(
#     stations: list[str],
#     distances: list[int],
#     battery_range: int,
# ) -> list[list[str]]:
#     """
#     Generate all valid charging plans by exhaustive combination.
#
#     Example:
#         stations = ["A", "B", "C", "D"]
#         distances = [100, 120, 100, 120, 100]
#     """
#     valid_plans: list[list[str]] = []
#
#     for r in range(1, len(stations) + 1):
#         for plan in combinations(stations, r):
#             charge_points = [-1]
#             for station in plan:
#                 charge_points.append(stations.index(station))
#             charge_points.append(len(stations))
#
#             is_valid = True
#             for i in range(len(charge_points) - 1):
#                 start = charge_points[i] + 1
#                 end = charge_points[i + 1] + 1
#                 distance = sum(distances[start:end])
#                 if distance > battery_range:
#                     is_valid = False
#                     break
#
#             if is_valid:
#                 valid_plans.append(list(plan))
#
#     return valid_plans
#
# To use brute force instead of DFS, swap the call in generate_valid_plans:
#     return generate_valid_plans_brute_force(
#         stations, distances, battery_range
#     )

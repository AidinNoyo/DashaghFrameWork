import inspect

def every(seconds=0, minutes=0, hours=0, days=0, catchup="run_once", global_tick=False):
    interval = seconds + minutes * 60 + hours * 3600 + days * 86400
    if interval <= 0:
        raise ValueError("every(...) interval must be greater than zero")

    def decorator(func):
        func._schedule = {
            "interval": interval,
            "catchup": catchup,
            "global_tick": global_tick,
        }
        return func

    return decorator

def global_tick_every(seconds=0, minutes=0, hours=0, days=0):
    return every(seconds=seconds, minutes=minutes, hours=hours, days=days, global_tick=True)
def collect_schedules(instance, item_id):
    normal = []
    globals_ = []
    for name, member in inspect.getmembers(instance, predicate=inspect.iscoroutinefunction):
        meta = getattr(member, "_schedule", None)
        if not meta:
            continue
        task_key = f"{item_id}.{name}"
        entry = {
            "task_key": task_key,
            "method": member,
            "interval": meta["interval"],
            "catchup": meta["catchup"],
            "item_id": item_id,
        }
        if meta["global_tick"]:
            globals_.append(entry)
        else:
            normal.append(entry)
    return normal, globals_
def discover_scheduled_methods(instance):
    result = []
    for attr_name in dir(instance.__class__):
        attr = getattr(instance.__class__, attr_name, None)
        schedule = getattr(attr, "_schedule", None)
        if schedule and not schedule.get("global_tick"):
            task_key = f"{instance.id}.{attr_name}"
            result.append((task_key, attr, schedule))
    return result

class Item:
    id = None
    name = None
    price = 0
    category = "misc"
    max_owned = None
    enabled = True

    def __init__(self):
        self._extra = {}

    async def on_purchase(self, context):
        pass

    async def on_remove(self, context):
        pass

    async def on_use(self, context):
        pass

    async def on_profile(self, context):
        pass

    def get(self, key, default=None):
        return self._extra.get(key, default)

    def apply_config(self, data):
        known = ("name", "price", "category", "max_owned", "enabled")
        for field in known:
            if field in data:
                setattr(self, field, data[field])
        for key, value in data.items():
            if key not in known:
                self._extra[key] = value


_ITEM_CLASSES = []


def item(item_id):
    def decorator(cls):
        cls.id = item_id
        _ITEM_CLASSES.append(cls)
        return cls
    return decorator


def registered_item_classes():
    return list(_ITEM_CLASSES)

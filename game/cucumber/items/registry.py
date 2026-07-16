from cucumber.items.base import registered_item_classes
from cucumber.events.bus import EventBus


class ItemRegistry:
    def __init__(self, config):
        self.config = config
        self._items = {}

    def load(self):
        items_file = self.config.file("items.yml").data or {}
        if "items" in items_file and isinstance(items_file["items"], dict):
            items_config = items_file["items"]
        else:
            items_config = items_file

        for cls in registered_item_classes():
            instance = cls()
            data = items_config.get(cls.id, {}) if isinstance(items_config, dict) else {}
            if data:
                instance.apply_config(data)
            self._items[cls.id] = instance
            EventBus.register_owner_handlers(instance)

    def get(self, item_id):
        return self._items.get(item_id)

    def all(self):
        return list(self._items.values())

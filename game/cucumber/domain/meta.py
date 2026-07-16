class Meta:
    def __init__(self, data):
        self._data = data

    @property
    def telegram_id(self):
        return self._data["telegram_id"]

    @property
    def username(self):
        return self._data.get("username")

    @property
    def first_name(self):
        return self._data.get("first_name")

    @property
    def last_name(self):
        return self._data.get("last_name")

    @property
    def language_code(self):
        return self._data.get("language_code", "en")

    @property
    def created_at(self):
        return self._data.get("created_at")

    @property
    def is_bot(self):
        return bool(self._data.get("is_bot", 0))

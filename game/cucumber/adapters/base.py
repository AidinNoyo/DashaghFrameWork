class Adapter:
    def __init__(self):
        self.engine = None

    def bind(self, engine):
        self.engine = engine

    async def send(self, chat_id, text):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError

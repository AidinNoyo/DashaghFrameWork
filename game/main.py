from cucumber import CucumberEngine, EventBus
from cucumber.adapters.aiogram_adapter import AiogramAdapter

from systems.juice_bonus import JuiceBonus
from systems.juice_generator import JuiceGenerator

engine = CucumberEngine(config_dir="./config", database_url="sqlite+aiosqlite:///game.db")
engine.load_items("items")
engine.load_commands("commands")

EventBus.register_owner_handlers(JuiceBonus())

_juice_gen = JuiceGenerator()

_original_start = engine.start
async def _patched_start():
    await _original_start()
    await _juice_gen.start()
engine.start = _patched_start

# engine.use(AiogramAdapter(token="8978911407:AAEIpUMeQvpPfvkQDP5myhjxg1ojdwKTSWE"))
# engine.run()

engine.use(AiogramAdapter(token="8978911407:AAEIpUMeQvpPfvkQDP5myhjxg1ojdwKTSWE"))

if __name__ == "__main__":
    engine.run()

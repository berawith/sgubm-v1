from src.infrastructure.database.models import init_db
from src.infrastructure.config.settings import get_config

config = get_config()
init_db(config.database.connection_string)
print("Database initialized successfully.")

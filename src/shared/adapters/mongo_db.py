import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot")


class MongoDBClient:
    """Cliente MongoDB sin Singleton pattern (Hexagonal Architecture DIP)."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        user: str = None,
        password: str = None,
        db_name: str = None,
    ):
        self._client = None
        self._host = host or Settings.MONGO_HOST
        self._port = port or Settings.MONGO_PORT
        self._user = user or Settings.MONGO_USER
        self._password = password or Settings.MONGO_PASSWORD
        self._db_name = db_name or Settings.MONGO_DB_NAME

    def get_client(self):
        if self._client is None:
            kwargs = {
                "host": self._host,
                "port": self._port,
                "serverSelectionTimeoutMS": 5000,
            }
            # Only add authentication if credentials are provided
            if self._user and self._password:
                kwargs["username"] = self._user
                kwargs["password"] = self._password
                kwargs["authSource"] = "admin"
            self._client = MongoClient(**kwargs)
        return self._client

    def get_database(self):
        return self.get_client()[self._db_name]

    def test_connection(self):
        try:
            self.get_client().admin.command("ping")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError):
            return False


_default_client = None


def get_database():
    """Factory function para obtener la BD (compatible con CLI composition root)."""
    global _default_client
    if _default_client is None:
        _default_client = MongoDBClient()
    return _default_client.get_database()


def test_connection():
    """Test conexión con BD."""
    global _default_client
    if _default_client is None:
        _default_client = MongoDBClient()
    return _default_client.test_connection()

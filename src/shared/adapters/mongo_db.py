import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
MONGO_USER = os.getenv("MONGO_USER", "root")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "rootpassword")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "appdb")


class MongoDBClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
        return cls._instance

    def get_client(self):
        if self._client is None:
            self._client = MongoClient(
                host=MONGO_HOST,
                port=MONGO_PORT,
                username=MONGO_USER,
                password=MONGO_PASSWORD,
                authSource="admin",
                serverSelectionTimeoutMS=5000,
            )
        return self._client

    def get_database(self):
        return self.get_client()[MONGO_DB_NAME]

    def test_connection(self):
        try:
            self.get_client().admin.command("ping")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError):
            return False


def get_database():
    return MongoDBClient().get_database()


def test_connection():
    return MongoDBClient().test_connection()

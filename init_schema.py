import logging
from pymongo import MongoClient
from pymongo.errors import CollectionInvalid  # optional: if תרצי לתפוס חריגות ביצירה
from dotenv import load_dotenv
import os

from schema_config import ensure_collections_and_indexes, get_allowed_collections

def init_schema():
    logging.basicConfig(
        filename="init_schema.log",
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    load_dotenv()
    MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("MONGODB_DB", "medical_db")

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    allowed = ", ".join(get_allowed_collections())
    print(f"🔹 Initializing '{DB_NAME}' at {MONGO_URI} (allowed: {allowed})")
    logging.info(f"Initializing '{DB_NAME}' at {MONGO_URI}")

    # single source to create collections + indexes
    ensure_collections_and_indexes(db)

    print("✅ Database and indexes are ready.")
    logging.info("Database and indexes are ready.")

if __name__ == "__main__":
    init_schema()

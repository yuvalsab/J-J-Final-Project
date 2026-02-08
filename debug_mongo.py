import os
from pymongo import MongoClient
print("MONGO_URI =", os.getenv("MONGO_URI"))
print("MONGO_DB  =", os.getenv("MONGO_DB"))


mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
db_name = os.getenv("MONGO_DB", "biosense")
lightning_name = os.getenv("LIGHTNING_NAME") or input("LIGHTNING NAME: ").strip()

c = MongoClient(mongo_uri)
db = c[db_name]

print("DB:", db_name)
print("Collections:", db.list_collection_names())

for col in db.list_collection_names():
    n = db[col].count_documents({"lightning_name": lightning_name})
    if n:
        print(col, "=>", n)
        doc = db[col].find_one({"lightning_name": lightning_name}, {"_id": 0})
        print("sample:", doc)

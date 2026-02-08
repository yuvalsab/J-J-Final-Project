"""
schema_config.py
----------------
Single source of truth for MongoDB schema 'nuances':
- Allowed collections
- Unique keys policy (by collection)
- Index specs (unique/sparse/index names)
"""

from typing import Dict, List, Tuple


# 1) Allowed collections (the only ones we work with)
ALLOWED_COLLECTIONS: List[str] = [
    "Procedures",
    "Errors",
    "Catheter",
    "Events",
]

def get_allowed_collections() -> List[str]:
    return list(ALLOWED_COLLECTIONS)


# 2) Unique-key policy (document-level uniqueness you care about)
#    Note: For Events we recommend a canonical 'event_key' (sorted join of event_ids)
UNIQUE_KEYS: Dict[str, Tuple[str, ...]] = {
    "Catheter":  ("lightning_name", "catheter_ids"),
    "Errors":    ("lightning_name", "error_ids"),
    "Events":    ("lightning_name", "event_key"),  # event_key = canonical (sorted) of event_ids
    # Procedures intentionally has no unique key here
}

def get_unique_keys(collection: str) -> Tuple[str, ...]:
    return UNIQUE_KEYS.get(collection, ())


# 3) Index specifications (created only by init)
#    For Events, we use 'sparse=True' to avoid blocking inserts while migrating to event_key.
INDEX_SPECS: Dict[str, List[dict]] = {
    "Catheter": [
        {
            "keys": [("lightning_name", 1), ("catheter_ids", 1)],
            "unique": True,
            "name": "uniq_catheter_lightning_id",
            "sparse": False,
        }
    ],
    "Errors": [
        {
            "keys": [("lightning_name", 1), ("error_ids", 1)],
            "unique": True,
            "name": "uniq_errors_lightning_errorid",
            "sparse": False,
        }
    ],
    "Events": [
        {
            "keys": [("lightning_name", 1), ("event_key", 1)],
            "unique": True,
            "name": "uniq_events_lightning_eventkey",
            "sparse": True,  # allow docs missing event_key during transition
        }
    ],
    # Procedures: add indexes here if you need in future
}

def get_index_specs(collection: str) -> List[dict]:
    return INDEX_SPECS.get(collection, [])


# 4) One-shot function to create collections + indexes (to be called by init only)
def ensure_collections_and_indexes(db) -> None:
    existing = set(db.list_collection_names())

    # Create collections if missing
    for name in ALLOWED_COLLECTIONS:
        if name not in existing:
            db.create_collection(name)

    # Create indexes according to INDEX_SPECS
    for col, specs in INDEX_SPECS.items():
        if col not in ALLOWED_COLLECTIONS:
            continue
        for spec in specs:
            db[col].create_index(
                spec["keys"],
                name=spec.get("name"),
                unique=spec.get("unique", False),
                sparse=spec.get("sparse", False),
            )

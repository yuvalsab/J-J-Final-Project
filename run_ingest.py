import logging
import argparse
from utils.txt_parser import extract_blocks_from_txt
from utils.mongo_connector import save_document, db, Collections, bulk_save_events
from extractors.event_parser import parse_event_block


def main(txt_path: str, lightning_name: str):
    logging.basicConfig(
        filename="ingest.log",
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    logging.info(f"Using lightning_name={lightning_name}")

    try:
        blocks = extract_blocks_from_txt(txt_path)
        logging.info(f"Extracted {len(blocks)} blocks from TXT")
    except Exception as e:
        logging.error(f"Failed to extract blocks from TXT {txt_path}: {e}")
        print(f"Failed to extract blocks from TXT {txt_path}: {e}")
        return

    total_blocks = len(blocks)
    saved_blocks = 0
    skipped_blocks = 0
    problematic_blocks = []
    pending_events = []

    for idx, block in enumerate(blocks, start=1):
        try:
            doc = parse_event_block(block, lightning_name)
            if doc:
                try:
                    if doc["_collection"] == Collections.Events:
                        pending_events.append(doc)
                        saved_blocks += 1
                    else:
                        save_document(doc)
                        saved_blocks += 1
                except Exception as e:
                    skipped_blocks += 1
                    problematic_blocks.append({
                        "index": idx,
                        "header": block[0] if block else "EMPTY",
                        "error": str(e),
                        "doc": doc
                    })
                    logging.error(f"Failed to save block {idx}: {e}")
            else:
                skipped_blocks += 1
                logging.warning(f"Skipped block {idx}: header='{block[0] if block else 'EMPTY'}'")
        except Exception as e:
            skipped_blocks += 1
            problematic_blocks.append({
                "index": idx,
                "header": block[0] if block else "EMPTY",
                "error": str(e),
                "doc": None
            })
            logging.error(f"Failed to parse block {idx}: {e}")

    if pending_events:
        try:
            bulk_save_events(pending_events)
        except Exception as e:
            logging.error(f"Failed bulk save events: {e}")
            for d in pending_events:
                try:
                    save_document(d)
                except Exception as ex:
                    logging.error(f"Failed fallback save for one event: {ex}")

    print("\n=== Summary Report ===")
    print(f"Total blocks: {total_blocks}")
    print(f"Saved: {saved_blocks}")
    print(f"Skipped: {skipped_blocks}")

    if problematic_blocks:
        print("\n⚠️ Some blocks had issues:")
        for pb in problematic_blocks:
            print(f" - Block {pb['index']}: header='{pb['header']}' → error='{pb['error']}'")

        choice = input("\nDo you want to DELETE documents related to problematic blocks from MongoDB? (y/n): ").strip().lower()
        if choice == "y":
            for pb in problematic_blocks:
                doc = pb.get("doc")
                if not doc or "_collection" not in doc:
                    continue

                key_filter = {}
                if doc["_collection"] == Collections.Catheter:
                    key_filter = {"lightning_name": doc["lightning_name"], "catheter_ids": doc.get("catheter_ids")}
                elif doc["_collection"] == Collections.Errors:
                    key_filter = {"lightning_name": doc["lightning_name"], "error_ids": doc.get("error_ids")}
                elif doc["_collection"] == Collections.Events:
                    key_filter = {"lightning_name": doc["lightning_name"], "event_ids": doc.get("event_ids")}

                if key_filter:
                    db[doc["_collection"]].delete_many(key_filter)
                    print(f"❌ Deleted from {doc['_collection']} with filter {key_filter}")
                    logging.info(f"Deleted from {doc['_collection']} with filter {key_filter}")

    logging.info(f"Summary: {saved_blocks}/{total_blocks} saved, {skipped_blocks} skipped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--txt", dest="txt_path", required=False)
    parser.add_argument("--lightning-name", dest="lightning_name", required=False)
    args = parser.parse_args()

    txt_path = args.txt_path or input("TXT path: ").strip()
    lightning_name = args.lightning_name or input("LIGHTNING NAME: ").strip()

    main(txt_path, lightning_name)

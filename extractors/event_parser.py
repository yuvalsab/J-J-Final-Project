import re
from utils.mongo_connector import Collections
from extractors.field_utils import BLOCK_FIELDS, get_block_fields, to_snake_case
from extractors.field_parser import parse_fields_inline_format

def parse_event_block(block_lines, lightning_name):
    """
    Parse a block of text into a MongoDB document structure.
    Determines collection based on block type.
    """
    if not block_lines:
        return None

    header = block_lines[0].strip().upper()
    body = block_lines[1:]

    block_name, valid_fields = get_block_fields(header)

    # Error ID block
    if "ERROR ID" in header:
        match = re.search(r"ERROR ID\s*(\d+)", header)
        error_id_from_header = match.group(1) if match else None
        doc_data, extra = parse_fields_inline_format(body, BLOCK_FIELDS["ERROR ID BLOCK"])
        if error_id_from_header:
            doc_data["error_id"] = error_id_from_header
        return {
            "lightning_name": lightning_name,
            "event_type": "error_id_block",
            **doc_data,
            "extra": extra,
            "_collection": Collections.Errors
        }

    # Catheter detail block
    if "CATHETER ID" in header:
        doc_data, extra = parse_fields_inline_format(body, BLOCK_FIELDS["CATHETER DETAIL BLOCK"])
        return {
            "lightning_name": lightning_name,
            "event_type": "catheter_detail_block",
            **doc_data,
            "extra": extra,
            "_collection": Collections.Catheter
        }

    # Known events
    if block_name:
        doc_data, extra = parse_fields_inline_format(body, valid_fields)
        return {
            "lightning_name": lightning_name,
            "event_type": to_snake_case(block_name),
            **doc_data,
            "extra": extra,
            "_collection": Collections.Events
        }

    # Unknown → ask user
    print("\n⚠️ Block not recognized automatically.")
    print(f"   ➤ Header: {block_lines[0].strip()}")
    print("\nChoose which collection to assign this block to:")
    print(f"  [1] {Collections.Events}")
    print(f"  [2] {Collections.Catheter}")
    print(f"  [3] {Collections.Errors}")
    print(f"  [4] {Collections.Procedures}")
    print("  [0] Not relevant – skip this block")

    try:
        choice = int(input("Enter choice (0–4): "))

        if choice == 1:   # Events
            doc_data, extra = parse_fields_inline_format(body, BLOCK_FIELDS["ABLATION EVENTS"])
            return {"lightning_name": lightning_name, "event_type": "manual_events_block",
                    **doc_data, "extra": extra, "_collection": Collections.Events}

        elif choice == 2:   # Catheter
            doc_data, extra = parse_fields_inline_format(body, BLOCK_FIELDS["CATHETER DETAIL BLOCK"])
            return {"lightning_name": lightning_name, "event_type": "manual_catheter_block",
                    **doc_data, "extra": extra, "_collection": Collections.Catheter}

        elif choice == 3:   # Errors
            doc_data, extra = parse_fields_inline_format(body, BLOCK_FIELDS["ERROR ID BLOCK"])
            return {"lightning_name": lightning_name, "event_type": "manual_error_block",
                    **doc_data, "extra": extra, "_collection": Collections.Errors}

        elif choice == 4:   # Procedures
            doc_data, extra = parse_fields_inline_format(body, set())
            return {"lightning_name": lightning_name, "event_type": "manual_procedure_block",
                    **doc_data, "extra": extra, "_collection": Collections.Procedures}

        else:
            print("➡️ Skipping block")
            return None

    except Exception:
        print("❌ Invalid input, skipping block")
        return None

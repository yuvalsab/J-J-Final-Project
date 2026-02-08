import re

# === Convert field names to snake_case ===
def to_snake_case(name: str) -> str:
    """
    Convert any string to snake_case.
    Example: 'Total Events' → 'total_events'
    """
    name = name.lower()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    return name.strip('_')


# === Define valid fields per block type (exact names from files) ===
BLOCK_FIELDS = {
    "ABLATION EVENTS": {
        "Total Events", "Ablation Sessions", "Event Type",
        "First Occurrence", "Last Occurrence", "Event IDs",
        "Total Duration", "Event Sessions"
    },
    "PACING EVENTS": {
        "Total Events", "Pacing Sessions", "Event Type",
        "First Occurrence", "Last Occurrence", "Event IDs",
        "Total Duration", "Event Sessions"
    },
    "MAGNETIC SENSOR EVENTS": {
        "Total Events", "Channels Monitored", "Critical Channels (18-20)",
        "Event Type", "First Occurrence", "Last Occurrence",
        "ERROR 105 CORRELATION", "Event IDs", "Total Duration", "Event Sessions"
    },
    "ERROR EVENTS": {
        "Total Events", "Event Type", "First Occurrence", "Last Occurrence",
        "Event IDs", "Error IDs", "Total Duration", "Event Sessions"
    },
    "CATHETER EVENTS": {
        "Total Events", "Event Type", "First Occurrence", "Last Occurrence",
        "Catheter IDs", "Total Duration", "Event Sessions",
        "Part Number", "Clinical Category", "Electrodes",
        "Thermocouples", "Capabilities", "Detailed event timeline"
    },
    "MAPPING EVENTS": {
        "Total Events", "Event Type", "First Occurrence", "Last Occurrence",
        "Event IDs", "Total Duration", "Event Sessions"
    },
    "HARDWARE EVENTS": {
        "Total Events", "Event Type", "First Occurrence", "Last Occurrence",
        "Event IDs", "Total Duration", "Event Sessions"
    },
    "PATCH EVENTS": {
        "Total Events", "Event Type", "First Occurrence", "Last Occurrence",
        "Event IDs", "Total Duration", "Event Sessions"
    },
    "ERROR ID BLOCK": {
        "Total Events", "Actual Error Occurrences", "Event Type",
        "First Occurrence", "Last Occurrence", "Error Frequency",
        "Event IDs", "Error IDs", "Total Duration"
    },
    "CATHETER DETAIL BLOCK": {
        "Total Events", "Event Type", "First Occurrence", "Last Occurrence",
        "Catheter Ids", "Catheter IDs", "Part Number",
        "Clinical Category", "Electrodes", "Thermocouples",
        "Capabilities", "Total Duration",
        "Catheter connection and disconnection event Sessions",
        "Detailed event timeline"
    }
}


def get_block_fields(header: str):
    """
    Return block type name and its valid fields based on the header.
    Example: "ABLATION EVENTS" → ("ABLATION EVENTS", {...fields...})
    """
    header = header.upper()
    for block_name, fields in BLOCK_FIELDS.items():
        if block_name in header:
            return block_name, fields
    return None, set()

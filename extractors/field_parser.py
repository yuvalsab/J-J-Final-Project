import re
from extractors.field_utils import to_snake_case

def parse_fields_inline_format(lines, valid_fields):
    """
    Parse block body into recognized fields + extra fields.
    
    Args:
        lines (list[str]): lines from block body
        valid_fields (set[str]): valid field names in original format
    
    Returns:
        (dict, dict): doc_data (recognized fields), extra_data (others)
    """
    doc_data, extra_data = {}, {}
    i = 0
    subfield_prefix_pattern = re.compile(r"^[\s]*[^A-Za-z0-9]")

    # Convert valid_fields to snake_case for comparison
    valid_snake = {to_snake_case(f) for f in valid_fields}

    while i < len(lines):
        line = lines[i].strip()

        if ":" in line:
            parts = line.split(":", 1)
            raw_key = parts[0].strip()
            value = parts[1].strip()
            snake_key = to_snake_case(raw_key)

            # Handle subfields → keep as list
            if value == "" and i + 1 < len(lines) and subfield_prefix_pattern.match(lines[i + 1]):
                sublines = []
                i += 1
                while i < len(lines) and subfield_prefix_pattern.match(lines[i]):
                    sublines.append(lines[i].strip())
                    i += 1
                (doc_data if snake_key in valid_snake else extra_data)[snake_key] = sublines
                continue

            # Normal case
            (doc_data if snake_key in valid_snake else extra_data)[snake_key] = value

        i += 1

    return doc_data, extra_data

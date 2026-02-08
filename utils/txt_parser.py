def is_equals_line(line: str) -> bool:
    s = line.strip()
    return len(s) >= 3 and set(s) == {"="}

def extract_blocks_from_txt(txt_path):
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]

    underline_idxs = [i for i, ln in enumerate(lines) if is_equals_line(ln) and i - 1 >= 0]

    blocks = []
    for idx, ul_i in enumerate(underline_idxs):
        header_i = ul_i - 1
        next_ul = underline_idxs[idx + 1] if idx + 1 < len(underline_idxs) else None

        start = ul_i + 1
        end = len(lines) if next_ul is None else max(start, next_ul - 2)

        block = [lines[header_i]] + lines[start:end]
        if block and block[0].strip():
            blocks.append(block)

    return blocks

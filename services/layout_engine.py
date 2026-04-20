"""
Layout Engine
===============
Performs spatial analysis of OCR word positions to group text
into lines, blocks, and page regions (header, body, footer).

Also detects key-value pairs for downstream data extraction.
"""

from config import LINE_Y_TOLERANCE, HEADER_RATIO, FOOTER_RATIO


def analyze_layout(ocr_data: dict) -> dict:
    """
    Analyze the spatial layout of OCR results.

    Args:
        ocr_data: Merged OCR result with 'words' and 'raw_text'.

    Returns:
        Dict containing lines, blocks, regions, and key-value pairs.
    """
    words = ocr_data.get("words", [])

    if not words:
        return {
            "lines": [],
            "blocks": {},
            "regions": {"header": [], "body": [], "footer": []},
            "key_value_pairs": [],
            "page_height": 0,
            "page_width": 0,
        }

    # Determine page dimensions
    page_height = max(w["y"] + w["h"] for w in words)
    page_width = max(w["x"] + w["w"] for w in words)

    # Group words into lines
    lines = _group_into_lines(words)

    # Group into blocks
    blocks = _group_into_blocks(words)

    # Classify regions
    regions = _classify_regions(lines, page_height)

    # Detect key-value pairs
    kv_pairs = _detect_key_value_pairs(lines)

    return {
        "lines": lines,
        "blocks": blocks,
        "regions": regions,
        "key_value_pairs": kv_pairs,
        "page_height": page_height,
        "page_width": page_width,
    }


def _group_into_lines(words: list) -> list:
    """
    Group words into lines based on Y-coordinate proximity.
    Words within LINE_Y_TOLERANCE pixels vertically are considered same line.
    """
    if not words:
        return []

    # Sort by y, then x
    sorted_words = sorted(words, key=lambda w: (w["y"], w["x"]))

    lines = []
    current_line = [sorted_words[0]]

    for word in sorted_words[1:]:
        # Check if this word is on the same line
        avg_y = sum(w["y"] for w in current_line) / len(current_line)
        if abs(word["y"] - avg_y) <= LINE_Y_TOLERANCE:
            current_line.append(word)
        else:
            # Sort current line by x position and save
            current_line.sort(key=lambda w: w["x"])
            lines.append({
                "words": current_line,
                "text": " ".join(w["text"] for w in current_line),
                "y": min(w["y"] for w in current_line),
                "x": min(w["x"] for w in current_line),
                "avg_conf": sum(w["conf"] for w in current_line) / len(current_line),
            })
            current_line = [word]

    # Don't forget the last line
    if current_line:
        current_line.sort(key=lambda w: w["x"])
        lines.append({
            "words": current_line,
            "text": " ".join(w["text"] for w in current_line),
            "y": min(w["y"] for w in current_line),
            "x": min(w["x"] for w in current_line),
            "avg_conf": sum(w["conf"] for w in current_line) / len(current_line),
        })

    return lines


def _group_into_blocks(words: list) -> dict:
    """Group words by their Tesseract block_num."""
    blocks = {}
    for word in words:
        block_id = word.get("block_num", 0)
        if block_id not in blocks:
            blocks[block_id] = []
        blocks[block_id].append(word)
    return blocks


def _classify_regions(lines: list, page_height: int) -> dict:
    """
    Classify lines into header, body, and footer regions
    based on their vertical position on the page.
    """
    header_cutoff = page_height * HEADER_RATIO
    footer_cutoff = page_height * FOOTER_RATIO

    regions = {"header": [], "body": [], "footer": []}

    for line in lines:
        y = line["y"]
        if y < header_cutoff:
            regions["header"].append(line)
        elif y > footer_cutoff:
            regions["footer"].append(line)
        else:
            regions["body"].append(line)

    return regions


def _detect_key_value_pairs(lines: list) -> list:
    """
    Detect key-value pairs in lines.
    Looks for patterns like "Label: Value" or "Label Value".
    """
    kv_pairs = []
    kv_separators = {":", "-", "=", "|"}

    for line in lines:
        text = line["text"]

        # Check for colon-separated key-value
        for sep in kv_separators:
            if sep in text:
                parts = text.split(sep, 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key and value and len(key) < 50:  # Key shouldn't be too long
                        kv_pairs.append({
                            "key": key,
                            "value": value,
                            "separator": sep,
                            "y": line["y"],
                            "x": line["x"],
                        })
                        break  # Only first separator match

    return kv_pairs

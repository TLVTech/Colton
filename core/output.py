import os
import csv
from typing import Union, List, Dict

def write_to_csv(data: Union[Dict, List[Dict]], attributes: List[str], filename: str) -> None:
    """
    Append one or more dicts to a CSV file, creating directories if needed.
    If attributes (fieldnames) are not provided, they will be inferred from data.
    """
    if isinstance(data, dict):
        data = [data]

    # Infer attributes if not provided
    if not attributes:
        attrs = set()
        for row in data:
            attrs.update(row.keys())
        attributes = sorted(attrs)

    parent = os.path.dirname(filename)
    if parent:
        os.makedirs(parent, exist_ok=True)

    file_exists = os.path.exists(filename)
    file_empty = (not file_exists) or (os.path.getsize(filename) == 0)

    with open(filename, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=attributes)
        if file_empty:
            writer.writeheader()
        for row in data:
            out_row = {attr: row.get(attr, "") for attr in attributes}
            writer.writerow(out_row)
    print(f"Data written to {filename} successfully.")
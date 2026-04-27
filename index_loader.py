import os
import requests

INDEX_PATH = "index.json"

def ensure_index_exists():
    if os.path.exists(INDEX_PATH):
        return

    index_url = os.getenv("AUCTIS_INDEX_URL")

    if not index_url:
        raise FileNotFoundError(
            "Missing index.json and no AUCTIS_INDEX_URL secret was set."
        )

    response = requests.get(index_url, timeout=120)
    response.raise_for_status()

    with open(INDEX_PATH, "wb") as f:
        f.write(response.content)
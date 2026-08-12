import requests
import json

# --- Auth ---
url = "https://login-stg.libris.kb.se/oauth/token"
payload = {
    "client_id": "client_id",           # your client ID
    "client_secret": "client_secret",       # your client secret
    "grant_type": "client_credentials"
}
headers = {
    'Content-Type': 'application/x-www-form-urlencoded'
}

response = requests.post(url, data=payload, headers=headers)
response.raise_for_status()

TOKEN = response.json().get('access_token')
print("TOKEN:", TOKEN)

BASE = "https://libris-stg.kb.se"

auth_headers = {
    "Authorization": f"Bearer {TOKEN}",   # <-- needs "Bearer " prefix
    "XL-Active-Sigel": "SEK"
}

with open("records.jsonl", "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, start=1):
        line = line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"Line {line_num}: invalid JSON, skipping ({e})")
            continue

        # The record's identifier lives in @graph[0]["@id"], e.g.
        # "https://id.kb.se/3qnv90h31d3z8wkj". The API endpoint for the
        # record uses the same trailing ID segment on the libris(-stg).kb.se host.
        try:
            graph_id = record["@graph"][0]["@id"]
        except (KeyError, IndexError):
            print(f"Line {line_num}: no @graph[0].@id found, skipping")
            continue

        record_id = graph_id.rstrip("/").split("/")[-1]
        record_url = f"{BASE}/{record_id}"

        # 1. GET the current live record first — both for the ETag, and to
        # get the record's *actual current* self-referencing IDs. Rather than
        # guessing how to rewrite id.kb.se vs id-stg.kb.se vs libris-stg.kb.se
        # ourselves, we copy whatever IDs the live record currently has.
        get_resp = requests.get(
            record_url,
            headers={**auth_headers, "Accept": "application/ld+json"}
        )
        if get_resp.status_code >= 400:
            print(f"Line {line_num}: GET failed {get_resp.status_code} -> {get_resp.text}")
            continue

        etag = get_resp.headers.get("ETag")
        if not etag:
            print(f"Line {line_num}: no ETag in GET response, skipping")
            continue

        try:
            live_record = get_resp.json()
            live_record_id = live_record["@graph"][0]["@id"]
            live_item_id = live_record["@graph"][1]["@id"]
        except (KeyError, IndexError, ValueError) as e:
            print(f"Line {line_num}: couldn't parse live record IDs, skipping ({e})")
            continue

        # --- DEBUG: compare live vs outgoing ---
        print(f"Line {line_num} DEBUG live_record_id: {live_record_id}")
        print(f"Line {line_num} DEBUG live_item_id:   {live_item_id}")
        print(f"Line {line_num} DEBUG record_url:     {record_url}")
        # ----------------------------------------

        # Overwrite the self-referencing IDs in our payload with the live
        # ones, so the update carries your new field values but keeps the
        # record's identity exactly as Libris currently has it.
        # Keep the Record wrapper (@graph[0]) exactly as Libris already has
        # it — it's server-managed (created/modified/recordStatus/
        # controlNumber etc.) and a PUT is a full swap-all, so submitting a
        # partial version of it causes a server error. Only the actual
        # entity content in @graph[1] comes from your update file.
        record["@graph"][0] = live_record["@graph"][0]
        record["@graph"][1]["@id"] = live_item_id

        record_json = json.dumps(record)

        # --- DEBUG: full live record and outgoing payload ---
        print(f"Line {line_num} DEBUG live record @graph[0]: {json.dumps(live_record['@graph'][0])}")
        print(f"Line {line_num} DEBUG outgoing @graph[0]:    {json.dumps(record['@graph'][0])}")
        # ------------------------------------------------------

        # 2. PUT the updated record with If-Match set to that ETag
        put_headers = {
            **auth_headers,
            "Content-Type": "application/ld+json",
            "If-Match": etag
        }
        put_resp = requests.put(record_url, headers=put_headers, data=record_json)

        # Success = 204 No Content -> no body to read
        print(f"Line {line_num}: {put_resp.status_code}")
        if put_resp.status_code == 409:
            print(f"  -> Conflict: record changed since GET, re-fetch and retry")
        elif put_resp.status_code >= 400:
            print(f"  -> {put_resp.text}")
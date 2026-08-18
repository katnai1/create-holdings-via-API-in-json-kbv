import requests
import json
from urllib.parse import urlparse

# --- Auth ---
url = "https://login.libris.kb.se/oauth/token"
payload = {
    "client_id": "",           # your client ID
    "client_secret": "",       # your client secret
    "grant_type": "client_credentials"
}
headers = {
    'Content-Type': 'application/x-www-form-urlencoded'
}

response = requests.post(url, data=payload, headers=headers)
response.raise_for_status()

TOKEN = response.json().get('access_token')
print("TOKEN:", TOKEN)

BASE = "https://libris.kb.se"

auth_headers = {
    "Authorization": f"Bearer {TOKEN}",   # <-- needs "Bearer " prefix
    "XL-Active-Sigel": "SEK"
}


def extract_record_id(line):
    """
    Accepts either a bare ID ('nszspbwt3rhpnpq') or a full URL
    ('https://libris.kb.se/nszspbwt3rhpnpq#it', with or without
    the #it fragment, and regardless of host).
    """
    line = line.strip()
    if not line:
        return None
    if line.startswith("http://") or line.startswith("https://"):
        path = urlparse(line).path  # drops the #it fragment automatically
        return path.rstrip("/").split("/")[-1]
    return line  # already a bare ID


# --- infile: one ID or URL per line ---
with open("records.txt", "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, start=1):
        record_id = extract_record_id(line)
        if not record_id:
            continue

        record_url = f"{BASE}/{record_id}"

        # 1. GET the current live record — embellished=false means we get
        # back just the bare record (Record wrapper + entity), with no
        # extra linked/related records appended to @graph. That's exactly
        # what's valid to PUT back.
        get_resp = requests.get(
            record_url,
            params={"embellished": "false"},
            headers={**auth_headers, "Accept": "application/ld+json"}
        )
        if get_resp.status_code >= 400:
            print(f"Line {line_num} ({record_id}): GET failed {get_resp.status_code} -> {get_resp.text}")
            continue

        etag = get_resp.headers.get("ETag")
        if not etag:
            print(f"Line {line_num} ({record_id}): no ETag in GET response, skipping")
            continue

        # No merging, no edits — PUT back exactly what we got
        live_record_json = get_resp.text

        # 2. PUT the record back with If-Match set to that ETag
        put_headers = {
            **auth_headers,
            "Content-Type": "application/ld+json",
            "If-Match": etag
        }
        put_resp = requests.put(record_url, headers=put_headers, data=live_record_json)

        # Success = 204 No Content -> no body to read
        print(f"Line {line_num} ({record_id}): {put_resp.status_code}")
        if put_resp.status_code == 409:
            print(f"  -> Conflict: record changed since GET, re-fetch and retry")
        elif put_resp.status_code >= 400:
            print(f"  -> {put_resp.text}")

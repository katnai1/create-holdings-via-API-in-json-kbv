import requests
import json

url = "https://login-stg.libris.kb.se/oauth/token"
payload = {
    "client_id": "client_if",           # your client ID
    "client_secret": "client_secret",   # your client secret
    "grant_type": "client_credentials"
}
headers = {
    'Content-Type': 'application/x-www-form-urlencoded'
}

response = requests.post(url, data=payload, headers=headers)
response.raise_for_status()  # Raise exception if token request fails

TOKEN = response.json().get('access_token')
print("TOKEN:", TOKEN)


URL = "https://libris-stg.kb.se/data"  # your create-record endpoint

headers = {
    "Authorization": f'Bearer {TOKEN}',
    "Content-Type": "application/ld+json",
    "XL-Active-Sigel": "SEK"
}

with open("records.jsonl", "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, start=1):
        line = line.strip()
        if not line:
            continue  # skip blank lines

        try:
            record = json.loads(line)  # validate it's proper JSON
        except json.JSONDecodeError as e:
            print(f"Line {line_num}: invalid JSON, skipping ({e})")
            continue

        #resp = requests.post(URL, headers=headers, data=json.dumps(record))
        #print("Sent headers:", resp.request.headers)
        #print(f"Line {line_num}: {resp.status_code}")
        #if resp.status_code >= 400:
            #print(f"  -> {resp.text}")

        resp = requests.post(URL, headers=headers, data=json.dumps(record))
        print(f"Line {line_num}: {resp.status_code}")
        if resp.status_code >= 400:
            print(f"  -> {resp.text}")

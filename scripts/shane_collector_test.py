import requests
import time
import os

API_TOKEN = "24b5c8102efcbc27e93429e9f18ba9a8bef51251357b3c1ae93773f303138b60"  # Your BrightData API key
COLLECTOR_ID = "c_mcuwb7kgy0gbasps8"

def trigger_collector():
    trigger_url = f"https://api.brightdata.com/dca/trigger?collector={COLLECTOR_ID}&queue_next=1"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    print("[🌐] Triggering Shane's Equipment collector job...")
    response = requests.post(trigger_url, headers=headers, json=[{}])
    print(f"[DEBUG] Status code: {response.status_code}")
    print(f"[DEBUG] Response text: {response.text}")
    response.raise_for_status()
    # Only try to extract the job id if response is as expected
    result = response.json()
    print(f"[DEBUG] Response JSON: {result}")
    job_id = result["collection_id"]
    print(f"[✅] Collector job triggered: Job ID = {job_id}")
    return job_id

def fetch_results(job_id, poll_interval=10, timeout=120):
    # Poll for job result (will take 10–60 seconds typically)
    result_url = f"https://api.brightdata.com/dca/dataset?id={job_id}"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
    }
    elapsed = 0
    print("[⏳] Waiting for job to finish (may take 30–90 seconds)...")
    while elapsed < timeout:
        r = requests.get(result_url, headers=headers)
        print(f"[DEBUG] Polling status: {r.status_code}, Content-Type: {r.headers.get('content-type', '')}")
        # Print a preview of body:
        print(f"[DEBUG] Body preview: {r.text[:300]}...")

        if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
            data = r.json()
            print(f"[✅] Job done, {len(data)} results found!")
            with open(f"results/shane_brightdata_results.json", "w", encoding="utf-8") as f:
                import json
                json.dump(data, f, indent=2)
            return data
        elif r.status_code == 202:
            time.sleep(poll_interval)
            elapsed += poll_interval
        else:
            time.sleep(poll_interval)
            elapsed += poll_interval
    print("[❌] Timeout waiting for collector job result.")
    return None


if __name__ == "__main__":
    job_id = trigger_collector()
    data = fetch_results(job_id)
    if data:
        # Example: print all vehicle URLs
        print("Vehicle links scraped:")
        for entry in data:
            # Adjust field name if needed (it may be "links" or "listing_url" or similar)
            print(entry)

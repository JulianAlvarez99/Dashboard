import httpx
import json

payload = {
    "tenant_id": 2,
    "role": "ADMIN",
    "curve_type": "stepped",
    "daterange": {
        "start_date": "2026-01-31",
        "end_date": "2026-02-01",
        "start_time": "00:00",
        "end_time": "23:59"
    },
    "end_date": "2026-02-01",
    "end_time": "23:59",
    "start_date": "2026-01-31",
    "start_time": "00:00",
    "downtime_threshold": 360,
    "include_raw": True,
    "interval": "minute",
    "line_id": 1
}

def main():
    req = httpx.post("http://localhost:8000/api/v1/dashboard/data", json=payload)
    print("Status Code:", req.status_code)
    try:
        data = req.json()
        print("Metadata response:")
        print(json.dumps(data.get("metadata", {}), indent=2))
        
        widgets = data.get("widgets", {})
        print(f"\nWidgets returned: {len(widgets)}")
        
        raw_data = data.get("raw_data", [])
        print(f"Raw data detections: {len(raw_data)}")
    except Exception as e:
        print("Error parsing JSON:", e)
        print("Raw response:")
        print(req.text)

if __name__ == "__main__":
    main()

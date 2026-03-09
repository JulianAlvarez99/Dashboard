import requests
try:
    response = requests.post(
        "http://localhost:8000/api/v1/dashboard/apply-filters",
        json={"filters": {"line_id": "1"}}
    )
    if response.ok:
        d = response.json()
        print(f"Status: {d['status']}")
        print(f"Tables: {d['tables_queried']}")
        print(f"Rows: {d['row_count']}")
        print(f"Query: {d['query']}")
    else:
        print(f"Failed: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Error: {e}")

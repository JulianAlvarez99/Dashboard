import urllib.request
import re

try:
    r = urllib.request.urlopen("http://localhost:5000/dashboard/")
    body = r.read().decode("utf-8")
    
    # Extract script tag content
    pattern = r'<script type="application/json" id="dashboard-config">(.*?)</script>'
    match = re.search(pattern, body, re.DOTALL)
    if match:
        print("FOUND SCRIPT TAG:")
        print(match.group(1)[:300] + "...")
    else:
        print("SCRIPT TAG NOT FOUND!")
        
except Exception as e:
    print("ERROR FETCHING HTML:", e)

import requests
import json
import logging
import http.client as http_client

# Replace with your actual values
scylla_token="",
account_id=929
cluster_id=34765

url = f"https://api.cloud.scylladb.com/account/{account_id}/cluster/{cluster_id}/delete"

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {scylla_token}',
    'Trace-Id': 'delete-cluster-debug-20240519'
}

# Enable HTTP debugging
http_client.HTTPConnection.debuglevel = 1
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

data = {
    "clusterName": "faisal-sc-cluster"
}

# Send POST request to deletion endpoint
response = requests.post(url, headers=headers, json=data, timeout=60)

# Output results
print("Status Code:", response.status_code)
print("Response Text:", response.text)
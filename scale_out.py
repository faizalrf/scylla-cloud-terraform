import requests
import json
import logging
import http.client as http_client

# Replace with your actual values
scylla_token=""
account_id=929
cluster_id=34765
dc_id = 34152
new_node_count = 6
instance_type_id = 65

base_url = "https://api.cloud.scylladb.com"
url = f"{base_url}/account/{account_id}/cluster/{cluster_id}/resize"

data = {
    "dcNodes": [
        {
            "dcId": dc_id,
            "wantedSize": new_node_count,
            "instanceTypeId": instance_type_id
        }
    ]
}

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {scylla_token}',
    'Trace-Id': 'python-script'
}

http_client.HTTPConnection.debuglevel = 1
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True


# Send POST request
response = requests.post(url, headers=headers, json=data, timeout=60)

# Output results
print("Status Code:", response.status_code)
print("Response Text:", response.text)
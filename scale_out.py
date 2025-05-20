import requests
import json
import logging
import http.client as http_client

# Replace with your actual values
scylla_token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjIzOGEwYjJmIn0.eyJzdWIiOiI5OTQyNjYxOS0wYzc3LTQzOGYtYWRhMS1mMjkwOGM2MWU5MGMiLCJ0eXBlIjoidXNlckFjY2Vzc1Rva2VuIiwidGVuYW50SWQiOiIyMzIyZDI2MC03NDg1LTQ5ZDAtOWMxYi02ZTk2YjE2ZWMzYzciLCJ1c2VySWQiOiI3ZDNlODc2YS0yMmEwLTRjNTctOTYzZS04YWNmMzhhMGMyMTciLCJhcHBsaWNhdGlvbklkIjoiYzEyOTdkY2ItODdjYi00NWEyLWI4OTItNzU3MzQ0YTQxMWMyIiwicm9sZXMiOlsiRkVUQ0gtUk9MRVMtQlktQVBJIl0sInBlcm1pc3Npb25zIjpbIkZFVENILVBFUk1JU1NJT05TLUJZLUFQSSJdLCJhdWQiOiIyMzhhMGIyZi0zNmVhLTRhZDgtODFkNy1lYWZkNWY1ZGY5M2IiLCJpc3MiOiJodHRwczovL2F1dGguY2xvdWQuc2N5bGxhZGIuY29tIiwiaWF0IjoxNzQ1Mzk4MjYzfQ.6MP8ss2o3EMH0Ipfbvvwnv39iVO57gsigvfhl4JbH1-DlOzYqPuz1mTmss8DKikT9qT0uE6ImBC2fyk5jraZcjbq_UKRWYPeCOdZZvN3fzdVo5MM9j8ZnvL_eYSPjQisIfUq-CLEYdg3h9wQybKAhxCU36JKAJGXmujKwyxoYnhIgY8gNnxGHHNc4JmQ6yaYIaH6MTFE-XV45C5alj1qNKMM8rnjuLipC43sRvrFLXaEc66XPkpfQm1nnocUavrOLTeW37um8fjKUGx291k89V9gHLsUgpTPYNJ5D0-n4jIsUnjcRERlD8_SwU-G6UcMQFH0jWxgF3jVciE5WJlr1Q"
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
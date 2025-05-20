import requests
import json

def get_instance_type_id(scylla_token, account_id, cluster_id):
    url = f"https://api.cloud.scylladb.com/account/{account_id}/cluster/{cluster_id}"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {scylla_token}',
        'Trace-Id': 'get-instance-type'
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Failed to get cluster info. Status: {response.status_code}")
        print("Response:", response.text)
        return

    cluster_info = response.json()
    print(json.dumps(cluster_info, indent=2))

# Example usage
get_instance_type_id(
    scylla_token="",
    account_id="929",
    cluster_id="34765"
)

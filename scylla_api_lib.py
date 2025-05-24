import requests
import yaml

def load_cluster_config(cluster_id):
    with open("variables.yml", "r") as file:
        config = yaml.safe_load(file)
    return config["clusters"][cluster_id]

def get_account_id(api_token):
    url = "https://api.cloud.scylladb.com/account/default"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Trace-Id": "python-script"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]["accountId"]

def fetch_clusters(api_token):
    account_id = get_account_id(api_token)
    url = f"https://api.cloud.scylladb.com/account/{account_id}/clusters"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Trace-Id": "cluster-status-script"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]["clusters"]

# Function to fetch supported regions and instances from Scylla Cloud API
def fetch_regions_and_instances(api_token):
    cloud = 1  # AWS
    url = f"https://api.cloud.scylladb.com/deployment/cloud-provider/{cloud}/regions?defaults=true"
    headers = {
        "Authorization": f"Bearer {api_token}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get("data", {})


# Function to fetch the dcId from the VPC peering API
def get_dc_id(api_token, account_id, cluster_id):
    url = f"https://api.cloud.scylladb.com/account/{account_id}/cluster/{cluster_id}/network/vpc/peer"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Trace-Id": "python-script"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json().get("data", [])
    if not data:
        raise ValueError("No VPC peering data found")
    return data[0]["dcId"]

# Function to validate instance type availability and return instance type ID
def get_instance_type_id(api_token, target_instance_type):
    data = fetch_regions_and_instances(api_token)
    instances = data.get("instances", [])
    for instance in instances:
        if instance["externalId"] == target_instance_type:
            return instance["id"]
    return None

def get_node_details(api_token, tf_cluster_id):
    account_id = get_account_id(api_token)
    print("Scylla Cloud Cluster ID:", tf_cluster_id)
    if not tf_cluster_id:
        return

    url = f"https://api.cloud.scylladb.com/account/{account_id}/cluster/{tf_cluster_id}/nodes?enriched=true"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_token}',
        'Trace-Id': 'get-node-details'
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to get node details. Status: {response.status_code}")
        print("Response:", response.text)
        return None
    return response.json()

def get_current_node_count(api_token, account_id, cluster_id):
    url = f"https://api.cloud.scylladb.com/account/{account_id}/cluster/{cluster_id}/nodes?enriched=true"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Trace-Id": "python-script"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    nodes = data.get("data", {}).get("nodes", [])
    return len(nodes)

def resize_cluster(api_token, cluster_id, new_node_count, instance_type_id):
    account_id = get_account_id(api_token)
    base_url = "https://api.cloud.scylladb.com"
    url = f"{base_url}/account/{account_id}/cluster/{cluster_id}/resize"
    dc_id = get_dc_id(api_token, account_id, cluster_id)
    if dc_id is None:
        raise ValueError("Data center ID not found")
        exit(1)
    if new_node_count <= 0:
        raise ValueError("New node count must be greater than 0")

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
        'Authorization': f'Bearer {api_token}',
        'Trace-Id': 'python-script'
    }

    response = requests.post(url, headers=headers, json=data, timeout=120)
    if response.status_code == 200:
        print("Cluster resize request submitted successfully.")
        return response
    else:
        print(f"Failed to submit cluster resize request: {response.status_code} - {response.text}")
        return None

def get_cluster_progress_data(api_token, cluster_id):
    # Get account ID
    account_id = get_account_id(api_token)

    # Get progress details
    url = f"https://api.cloud.scylladb.com/account/{account_id}/cluster/{cluster_id}/request"
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Trace-Id': 'progress-fetch'
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to get progress details. Status: {response.status_code}")
        print("Response:", response.text)
        return
    return response.json()

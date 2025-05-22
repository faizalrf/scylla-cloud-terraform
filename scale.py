import requests
import json
import logging
import http.client as http_client
import yaml
import subprocess
import argparse

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

def get_current_node_count(api_token, account_id, cluster_id):
    url = f"https://api.cloud.scylladb.com/account/{account_id}/cluster/{cluster_id}/nodes?enriched=true"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Trace-Id": "python-script"
    }
    response = requests.get(url, headers=headers)
    print(json.dumps(response.json(), indent=2))
    response.raise_for_status()
    data = response.json().get("data", {})
    nodes = data.get("nodes", [])
    return len(nodes)

def get_terraform_output():
    try:
        output = subprocess.check_output(["terraform", "output", "-json"])
        return json.loads(output.decode())
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to run terraform output: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse terraform output JSON: {e}")

def main():
    parser = argparse.ArgumentParser(description="Scale Scylla Cloud cluster nodes")
    parser.add_argument("--terraform-dir", default=".", help="Directory containing terraform configuration")

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--in', dest='scale_in', action='store_true', help="Scale in to original node count")
    mode_group.add_argument('--out', dest='scale_out', action='store_true', help="Scale out to increased node count")

    args = parser.parse_args()

    # Load config from variables.yml
    with open("variables.yml", "r") as f:
        config = yaml.safe_load(f)

    region_name = list(config["regions"].keys())[0]
    region_config = config["regions"][region_name]

    # Extract required values
    scylla_token = config["scylla_api_token"]
    account_id = config["scylla_account_id"]
    terraform_output = get_terraform_output()
    cluster_id = terraform_output["scylladbcloud_cluster_id"]["value"]
    dc_id = get_dc_id(scylla_token, account_id, cluster_id)

    if dc_id is None:
        raise ValueError(f"Data center ID not found for region '{region_name}'")

    current_node_count = get_current_node_count(scylla_token, account_id, cluster_id)
    print(f"Current Node Count: {current_node_count}")

    if args.scale_out:
        new_node_count = region_config["nodes"] + region_config["scale_nodes"]
    else:
        new_node_count = region_config["nodes"]

    if current_node_count == new_node_count:
        print(f"Cluster is already at desired size: {new_node_count} nodes. No resize needed.")
        return

    instance_type_id = get_instance_type_id(scylla_token, region_config["scylla_scale_node_type"])
    if instance_type_id is None:
        raise ValueError(f"Instance type ID not found for instance type '{region_config['scylla_scale_node_type']}'")

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

if __name__ == "__main__":
    main()

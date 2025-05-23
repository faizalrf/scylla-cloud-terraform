import requests
import json
import logging
import http.client as http_client
import yaml
import subprocess
import argparse
import os

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
    response.raise_for_status()
    data = response.json().get("data", {})
    nodes = data.get("nodes", [])
    return len(nodes)

def get_terraform_output(terraform_dir="."):
    try:
        cwd = os.getcwd()
        os.chdir(terraform_dir)
        output = subprocess.check_output(["terraform", "output", "-json"])
        return json.loads(output.decode())
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to run terraform output: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse terraform output JSON: {e}")
    finally:
        os.chdir(cwd)

def get_account_id(api_token):
    url = "https://api.cloud.scylladb.com/account/default"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Trace-Id": "python-script"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]["accountId"]

def main():
    parser = argparse.ArgumentParser(description="Scale Scylla Cloud cluster nodes")
    parser.add_argument("--cluster", required=True, help="Cluster ID to use for selecting terraform output folder")

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--in', dest='scale_in', action='store_true', help="Scale in to original node count")
    mode_group.add_argument('--out', dest='scale_out', action='store_true', help="Scale out to increased node count")

    args = parser.parse_args()
    cluster_id = args.cluster

    # Load config from variables.yml
    with open("variables.yml", "r") as f:
        config = yaml.safe_load(f)

    # Extract only the 'clusters' dictionary
    clusters = config.get('clusters', {})

    # Get the specific cluster configuration
    cluster_config = clusters.get(cluster_id)

    region_name = list(cluster_config["regions"].keys())[0]
    region_config = cluster_config["regions"][region_name]

    # Extract required values
    scylla_token = cluster_config["scylla_api_token"]
    account_id = get_account_id(scylla_token)
    terraform_output = get_terraform_output(os.path.join("clusters", cluster_id, "terraform"))
    sc_cluster_id = terraform_output["scylladbcloud_cluster_id"]["value"]
    dc_id = get_dc_id(scylla_token, account_id, sc_cluster_id)

    if dc_id is None:
        raise ValueError(f"Data center ID not found for region '{region_name}'")

    current_node_count = get_current_node_count(scylla_token, account_id, sc_cluster_id)
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
    url = f"{base_url}/account/{account_id}/cluster/{sc_cluster_id}/resize"

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

    response = requests.post(url, headers=headers, json=data, timeout=120)

    print(f"Cluster Resize Request Submitted")
    print("---------------------------------")    
    if response.status_code == 200:
        resp_json = response.json().get("data", {})
        print(f"- Status     : {resp_json.get('status')}")
        print(f"- Request ID : {resp_json.get('id')}")
        print(f"- Cluster ID : {resp_json.get('clusterId')}")
        print(f"- Progress   : {resp_json.get('progressPercent')}%")
    else:
        print(f"- Status Code: {response.status_code}")
        print(f"- Response   : {response.text}")

if __name__ == "__main__":
    main()

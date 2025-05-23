def get_account_id(scylla_token):
    response = requests.get(
        "https://api.cloud.scylladb.com/account/default",
        headers={
            'Authorization': f'Bearer {scylla_token}',
            'Trace-Id': 'account-fetch'
        }
    )
    response.raise_for_status()
    return response.json()["data"]["accountId"]
import requests
import json
import yaml
import subprocess
from tabulate import tabulate
import argparse
from urllib.parse import urljoin


def load_cluster_config(cluster_id):
    with open("variables.yml", "r") as file:
        config = yaml.safe_load(file)
    return config["clusters"][cluster_id]

def get_terraform_output(cluster_id):
    tf_dir = f"clusters/{cluster_id}/terraform"
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=tf_dir,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print("Terraform output failed:", result.stderr)
        return None
    output = json.loads(result.stdout)
    return output.get("scylladbcloud_cluster_id", {}).get("value")

def print_cluster_info_table(cluster_info):
    data = []
    for key, value in cluster_info.get("data", {}).items():
        data.append([key, json.dumps(value, indent=2) if isinstance(value, (dict, list)) else value])
    print(tabulate(data, headers=["Key", "Value"], tablefmt="fancy_grid"))

def get_node_details(cluster_id):
    config = load_cluster_config(cluster_id)
    scylla_token = config["scylla_api_token"]
    account_id = get_account_id(scylla_token)
    tf_cluster_id = get_terraform_output(cluster_id)
    print("Scylla Cloud Cluster ID:", tf_cluster_id)
    if not tf_cluster_id:
        return

    url = f"https://api.cloud.scylladb.com/account/{account_id}/cluster/{tf_cluster_id}/nodes?enriched=true"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {scylla_token}',
        'Trace-Id': 'get-node-details'
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to get node details. Status: {response.status_code}")
        print("Response:", response.text)
        return

    nodes_info = response.json()
    nodes = nodes_info.get("data", {}).get("nodes", [])
    table_data = []
    for node in nodes:
        row = [
            node.get("privateIp"),
            node.get("status"),
            node.get("state"),
            node.get("region", {}).get("dcName"),
            node.get("instance", {}).get("externalId"),
            node.get("instance", {}).get("memory")/1024,
            node.get("instance", {}).get("totalStorage"),
            node.get("instance", {}).get("cpuCount"),
            node.get("instance", {}).get("networkSpeed")/1024,
            node.get("dataCenter", {}).get("cidrBlock")
        ]
        table_data.append(row)

    headers = ["Private IP", "Status", "State", "Region DC Name", "Instance Type", "Memory (GB)", "Storage (GB)", "vCPUs", "Net Speed (Gbps)", "CIDR Block"]
    print(tabulate(table_data, headers=headers, tablefmt="fancy_grid"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get node or progress details for a Scylla cluster.")
    parser.add_argument("--cluster", required=True, help="Cluster ID to fetch details for.")
    parser.add_argument("--progress", action="store_true", help="Fetch progress of current operations.")
    args = parser.parse_args()

    if args.progress:
        def get_cluster_progress(cluster_id):
            config = load_cluster_config(cluster_id)
            scylla_token = config["scylla_api_token"]
            tf_cluster_id = get_terraform_output(cluster_id)

            if not tf_cluster_id:
                print("No valid cluster ID from Terraform output.")
                return

            # Get account ID
            account_id = get_account_id(scylla_token)

            # Get progress details
            url = f"https://api.cloud.scylladb.com/account/{account_id}/cluster/{tf_cluster_id}/request"
            headers = {
                'Authorization': f'Bearer {scylla_token}',
                'Trace-Id': 'progress-fetch'
            }

            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Failed to get progress details. Status: {response.status_code}")
                print("Response:", response.text)
                return

            data = response.json().get("data", [])
            if not data:
                print("No ongoing operations found.")
                return

            table_data = []
            for item in data:
                table_data.append([
                    item.get("accountId"),
                    item.get("clusterId"),
                    item.get("progressDescription"),
                    item.get("progressPercent"),
                    item.get("requestType"),
                    item.get("status"),
                    item.get("userFriendlyError")
                ])
            headers = ["Account ID", "Cluster ID", "Progress Description", "Progress %", "Request Type", "Status", "Error"]
            print(tabulate(table_data, headers=headers, tablefmt="fancy_grid"))

        get_cluster_progress(args.cluster)
    else:
        get_node_details(args.cluster)

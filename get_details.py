from prettytable import PrettyTable
from scylla_api_lib import (
    load_cluster_config,
    get_cluster_progress_data,
    get_node_details
)

import json
import subprocess
from tabulate import tabulate
import argparse

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

def process_nodes_data(scylla_token, tf_cluster_id):
    nodes_info = get_node_details(scylla_token, tf_cluster_id)
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

    table = PrettyTable()
    table.field_names = ["Private IP", "Status", "State", "Region DC Name", "Instance Type", "Memory (GB)", "Storage (GB)", "vCPUs", "Net Speed (Gbps)", "CIDR Block"]
    for field in table.field_names:
        table.align[field] = "l"
    for row in table_data:
        table.add_row(row)
    print(table)

def process_progress_data(scylla_token, tf_cluster_id):
    progress_data = get_cluster_progress_data(scylla_token, tf_cluster_id)
    if not progress_data:
        print("No progress data available.")
        return

    table = PrettyTable()
    table.field_names = ["Account ID", "Cluster ID", "Progress Description", "Progress %", "Request Type", "Status", "User-Friendly Error"]
    for field in table.field_names:
        table.align[field] = "l"
    for operation in progress_data.get("data", []):
        row = [
            operation.get("accountId"),
            operation.get("clusterId"),
            operation.get("progressDescription"),
            operation.get("progressPercent"),
            operation.get("requestType"),
            operation.get("status"),
            operation.get("userFriendlyError")
        ]
        table.add_row(row)
    print(table)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get node or progress details for a Scylla cluster.")
    parser.add_argument("--cluster", required=True, help="Cluster ID to fetch details for.")
    parser.add_argument("--progress", action="store_true", help="Fetch progress of current operations.")
    args = parser.parse_args()
    cluster_id = args.cluster

    config = load_cluster_config(cluster_id)
    scylla_token = config["scylla_api_token"]
    tf_cluster_id = get_terraform_output(cluster_id)
    if not tf_cluster_id:
        exit(1)

    if args.progress:
        process_progress_data(scylla_token, tf_cluster_id)
    else:
        process_nodes_data(scylla_token, tf_cluster_id)

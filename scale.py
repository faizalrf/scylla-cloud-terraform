import json
import yaml
import subprocess
import argparse
import os
from scylla_api_lib import (
    get_account_id,
    get_dc_id,
    get_current_node_count,
    get_instance_type_id,
    resize_cluster
)

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

    response = resize_cluster(scylla_token, sc_cluster_id, new_node_count, instance_type_id)

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

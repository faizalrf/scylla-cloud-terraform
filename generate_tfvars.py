import argparse
import yaml
import json

def read_config(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def generate_terraform_vars(config, cluster_id):
    region_name = next(iter(config["regions"]))
    region = config["regions"][region_name]

    terraform_vars = {
        "scylla_api_token": config["scylla_api_token"],
        "cloud": config["cloud"].upper(),
        "scylla_cluster_name": config["cluster_name"],
        "scylla_version": config["scylla_version"],
        "region": region_name,
        "nodes": region["nodes"],
        "node_type": region["scylla_node_type"],
        "loader_vpc_region": region["loader_vpc_region"],
        "scale_nodes": region["scale_nodes"],
        "scale_node_type": region["scylla_scale_node_type"],
        "path_to_key": config["path_to_key"],
        "path_to_private_key": config["path_to_private_key"],
    }

    with open(f"clusters/{cluster_id}/terraform/terraform.auto.tfvars.json", "w") as tf_file:
        json.dump(terraform_vars, tf_file, indent=2)

def generate_loader_vars(config, cluster_id):
    region_name = next(iter(config["regions"]))
    region = config["regions"][region_name]

    loaders_terraform_vars = {
        "cloud": config["cloud"].upper(),
        "scylla_cluster_name": config["cluster_name"],
        "scylla_version": config["scylla_version"],
        "loader_vpc_region": region["loader_vpc_region"],
        "loaders": region["loaders"],
        "loaders_type": region["loaders_type"],
        "key_name": config["key_name"],
        "path_to_key": config["path_to_key"],
        "path_to_private_key": config["path_to_private_key"],
    }

    with open(f"clusters/{cluster_id}/ansible/terraform.auto.tfvars.json", "w") as tf_file:
        json.dump(loaders_terraform_vars, tf_file, indent=2)

def main(config, cluster_id):
    generate_terraform_vars(config, cluster_id)
    generate_loader_vars(config, cluster_id)

    print("terraform.auto.tfvars.json generated successfully.")

if __name__ == "__main__":
    # Initialize argument parser
    parser = argparse.ArgumentParser(description="ScyllaDB Cloud Cluster Setup")
    parser.add_argument("--cluster", required=True, help="Cluster ID to configure")

    try:
        # Parse arguments
        args = parser.parse_args()
    except SystemExit:
        print("Error: Missing required argument --cluster")
        print("Usage: python script.py --cluster-id <cluster_id>")
        exit(1)

    # Parse arguments
    args = parser.parse_args()
    cluster_id = args.cluster

    # Load YAML configuration
    config = read_config("variables.yml")  # Ensure correct path

    # Extract only the 'clusters' dictionary
    clusters = config.get('clusters', {})

    # Get the specific cluster configuration
    cluster_config = clusters.get(cluster_id)

    if not cluster_config:
        print(f"Error: Cluster '{cluster_id}' not found in variables.yml!")
        exit(1)

    # Now `cluster_config` contains only the data for the requested cluster
    print(f"Extracted configuration for cluster '{cluster_id}':")
    main(cluster_config, cluster_id)

import argparse
import yaml
import json
import sys, os, tempfile

def load_cluster_config(cluster_id):
    with open("variables-source.yml", "r") as source_file:
        all_clusters = yaml.safe_load(source_file)

    clusters = all_clusters.get("clusters", {})
    if cluster_id not in clusters:
        print(f"Cluster ID '{cluster_id}' not found in variables-source.yml")
        sys.exit(1)

    selected_cluster = clusters[cluster_id]

    # Write to temp file first
    with tempfile.NamedTemporaryFile("w", delete=False, dir=".", suffix=".yml") as tmp_file:
        yaml.dump(selected_cluster, tmp_file, sort_keys=False)
        temp_path = tmp_file.name

    # Atomically replace variables.yml
    os.replace(temp_path, "variables.yml")

    return selected_cluster

def generate_terraform_vars(config):
    region_name = next(iter(config["regions"]))
    region = config["regions"][region_name]

    terraform_vars = {
        "scylla_api_token": config["scylla_api_token"],
        "cloud": config["cloud"].upper(),
        "scylla_cluster_name": config["cluster_name"],
        "scylla_version": config["scylla_version"],
        "region": region_name,
        "scylla_cidr": region["cidr"],
        "nodes": region["nodes"],
        "node_type": region["scylla_node_type"],
        "loader_vpc_aws_account_id": region["loader_vpc_aws_account_id"],
        "loader_vpc_region": region["loader_vpc_region"],
        "loader_vpc": region["loader_vpc"],
        "loader_route_table": region["loader_route_table"],
        "scale_nodes": region["scale_nodes"],
        "scale_node_type": region["scylla_scale_node_type"],
        "path_to_key": config["path_to_key"],
        "path_to_private_key": config["path_to_private_key"],
    }

    with open("terraform.auto.tfvars.json", "w") as tf_file:
        json.dump(terraform_vars, tf_file, indent=2)

def generate_loader_vars(config):
    region_name = next(iter(config["regions"]))
    region = config["regions"][region_name]

    loaders_terraform_vars = {
        "cloud": config["cloud"].upper(),
        "scylla_version": config["scylla_version"],
        "scylla_cidr": region["cidr"],
        "loader_vpc_region": region["loader_vpc_region"],
        "loader_vpc": region["loader_vpc"],
        "loaders": region["loaders"],
        "loaders_type": region["loaders_type"],
        "key_name": config["key_name"],
        "path_to_key": config["path_to_key"],
        "path_to_private_key": config["path_to_private_key"],
    }

    with open("ansible/terraform.auto.tfvars.json", "w") as tf_file:
        json.dump(loaders_terraform_vars, tf_file, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Generate Terraform vars from cluster config")
    parser.add_argument("--cluster-id", required=True, help="Cluster ID from variables-source.yml")
    args = parser.parse_args()

    config = load_cluster_config(args.cluster_id)
    generate_terraform_vars(config)
    generate_loader_vars(config)

    print("✅ terraform.auto.tfvars.json generated successfully.")

if __name__ == "__main__":
    main()

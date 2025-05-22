import yaml, os
import argparse

def read_config(file_path):
    base_dir = os.path.dirname(__file__)
    full_path = os.path.join(base_dir, file_path)

    with open(full_path, 'r') as file:
        data = yaml.safe_load(file)
    return data.get("clusters", {})

if __name__ == "__main__":
    # Initialize argument parser
    parser = argparse.ArgumentParser(description="ScyllaDB Cluster Setup")
    parser.add_argument("--cluster", required=True, help="Cluster name to configure")

    try:
        # Parse arguments
        args = parser.parse_args()
    except SystemExit:
        print("Error: Missing required argument --cluster")
        print("Usage: python script.py --cluster <cluster_name>")
        exit(1)

    # Parse arguments
    args = parser.parse_args()
    cluster_id = args.cluster

    # Load YAML configuration
    clusters = read_config("variables.yml")  # Ensure correct path

    # Get the specific cluster configuration
    cluster_config = clusters.get(cluster_id)

    if not cluster_config:
        print(f"Error: Cluster '{cluster_id}' not found in variables.yml!")
        exit(1)

    print(f"{cluster_config['cloud']}:{cluster_config['scylla_version']}" if cluster_config else '')


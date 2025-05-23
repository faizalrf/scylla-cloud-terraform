import yaml
from prettytable import PrettyTable
from scylla_api_lib import (
    fetch_clusters,
    get_account_id,
    get_node_type_summary
)

def parse_variables_yml(filepath):
    with open(filepath, 'r') as file:
        return yaml.safe_load(file).get("clusters", {})

def main():
    config = parse_variables_yml("variables.yml")
    all_clusters = []
    api_token = None
    for _, cluster_config in config.items():
        api_token = cluster_config.get("scylla_api_token")
        if api_token:
            break

    account_id = get_account_id(api_token)
    for cluster_id, data in config.items():
        if not api_token:
            print(f"No API token found for cluster {cluster_id}, skipping.")
            continue
        try:
            clusters = fetch_clusters(api_token)
            cluster_lookup = {c['clusterName']: c for c in clusters}
        except Exception as e:
            print(f"Error fetching clusters for {cluster_id}: {e}")
            continue

        cluster_name = data.get("cluster_name")
        scylla_version = data.get("scylla_version")
        cloud = data.get("cloud")

        cluster_data = cluster_lookup.get(cluster_name)
        
        if cluster_data:
            status = cluster_data.get("status", "UNKNOWN")
            cs_cluster_id = cluster_data.get("id")
            summary = get_node_type_summary(api_token, account_id, cs_cluster_id)
            node_summary = ", ".join([f"{k}: {v}" for k, v in summary.items()])
        else:
            status = "NOT PROVISIONED"
            node_summary = ""

        all_clusters.append([
            cluster_id,
            cluster_name,
            scylla_version,
            cloud,
            node_summary,
            status
        ])

    table = PrettyTable()
    table.field_names = ["Cluster ID", "Cluster Name", "Scylla Version", "Cloud", "Node Summary", "Status"]
    for row in all_clusters:
        table.add_row(row)
    for field in table.field_names:
        table.align[field] = "l"

    print(table)

if __name__ == "__main__":
    main()
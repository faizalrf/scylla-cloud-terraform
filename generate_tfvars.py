import yaml
import json

with open("variables.yml", "r") as file:
    config = yaml.safe_load(file)

region_name = next(iter(config["regions"]))
region = config["regions"][region_name]

terraform_vars = {
    "scylla_api_token": config["scylla_api_token"],
    "cloud": config["cloud"].upper(),
    "scylla_cluster_name": config["cluster_name"],
    "scylla_version": config["scylla_version"],
    "region": region_name,
    "scylla_CIDR": region["cidr"],
    "nodes": region["nodes"],
    "node_type": region["scylla_node_type"],
    "scale_nodes": region["scale_nodes"],
    "scale_node_type": region["scylla_scale_node_type"],
    "path_to_key": config["path_to_key"],
    "path_to_private_key": config["path_to_private_key"],
}

with open("terraform.auto.tfvars.json", "w") as tf_file:
    json.dump(terraform_vars, tf_file, indent=2)

loaders_terraform_vars = {
    "cloud": config["cloud"].upper(),
    "scylla_version": config["scylla_version"],
    "region": region_name,
    "loader_vpc": region["loader_vpc"],
    "loaders": region["loaders"],
    "loaders_type": region["loaders_type"],
    "key_name": config["key_name"],
    "path_to_key": config["path_to_key"],
    "path_to_private_key": config["path_to_private_key"],
}

with open("loaders/terraform.auto.tfvars.json", "w") as tf_file:
    json.dump(loaders_terraform_vars, tf_file, indent=2)

print("✅ terraform.auto.tfvars.json generated successfully.")
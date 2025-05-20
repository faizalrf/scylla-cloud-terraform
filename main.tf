terraform {
  required_providers {
    scylladbcloud = {
      source = "scylladb/scylladbcloud"
      version = "1.8.1"
    }
  }
}

# fetch machine's public IP address
data "http" "myip" {
  url = "http://ipv4.icanhazip.com"
}

provider "scylladbcloud" {
  token = trim(var.scylla_api_token, " ")
}

# Create a cluster on AWS cloud.
resource "scylladbcloud_cluster" "sc_cluster" {
  name               = trim(var.scylla_cluster_name, " ")
  cloud              = trim(var.cloud, " ")
  region             = trim(var.region, " ")
  node_count         = var.nodes
  cidr_block         = trim(var.scylla_CIDR, " ")
  node_type          = trim(var.node_type, " ")
  scylla_version     = trim(var.scylla_version, " ")
  enable_vpc_peering = true
  enable_dns         = true
}

output "scylladbcloud_cluster_id" {
  value = scylladbcloud_cluster.sc_cluster.id
}
output "scylla_private_ips" {
  value = scylladbcloud_cluster.sc_cluster.node_private_ips
}
data "scylladbcloud_cql_auth" "cql_auth" {
  cluster_id = scylladbcloud_cluster.sc_cluster.id
}
output "scylla_cql_username" {
  description = "CQL username for Scylla Cloud cluster"
  value       = data.scylladbcloud_cql_auth.cql_auth.username
}
output "scylla_cql_password" {
  description = "CQL password for Scylla Cloud cluster"
  value       = data.scylladbcloud_cql_auth.cql_auth.password
  sensitive   = true
}
output "scylladbcloud_cluster_datacenter" {
  value = scylladbcloud_cluster.sc_cluster.datacenter
}
# Add a CIDR block to allowlist for the specified cluster.
resource "scylladbcloud_allowlist_rule" "whitelist" {
  depends_on = [scylladbcloud_cluster.sc_cluster]
  cluster_id = scylladbcloud_cluster.sc_cluster.id
  cidr_block = "${chomp(data.http.myip.response_body)}/32"
}
output "scylladbcloud_allowlist_rule_id" {
  value = scylladbcloud_allowlist_rule.whitelist.rule_id
}

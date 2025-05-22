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
  cidr_block         = trim(var.scylla_cidr, " ")
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

# End-to-end example for ScyllaDB Datacenter VPC peering on AWS.
data "aws_caller_identity" "current" {}

data "aws_vpc" "loader_vpc" {
  id = var.loader_vpc
}

resource "scylladbcloud_vpc_peering" "sc_peering" {
    cluster_id = scylladbcloud_cluster.sc_cluster.id
    datacenter = scylladbcloud_cluster.sc_cluster.datacenter

    peer_vpc_id      = var.loader_vpc
    peer_cidr_blocks = [data.aws_vpc.loader_vpc.cidr_block]  # List of blocks to allow
    peer_region      = var.loader_vpc_region
    peer_account_id  = data.aws_caller_identity.current.account_id

    allow_cql = true
}

resource "aws_vpc_peering_connection_accepter" "app" {
    vpc_peering_connection_id = scylladbcloud_vpc_peering.sc_peering.connection_id
    auto_accept               = true
}

resource "aws_route" "peering_route" {
  route_table_id            = var.loader_route_table
  destination_cidr_block    = var.scylla_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection_accepter.app.vpc_peering_connection_id
}

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
resource "scylladbcloud_cluster" "test_cluster" {
  name               = trim(var.scylla_cluster_name, " ")
  cloud              = "AWS"
  region             = trim(var.region, " ")
  node_count         = 3
  node_type          = trim(var.node_type, " ")
  scylla_version     = trim(var.scylla_version, " ")
  enable_vpc_peering = true
  enable_dns         = true
}

output "scylladbcloud_cluster_id" {
  value = scylladbcloud_cluster.test_cluster.id
}

output "scylladbcloud_cluster_datacenter" {
  value = scylladbcloud_cluster.test_cluster.datacenter
}

# Add a CIDR block to allowlist for the specified cluster.
resource "scylladbcloud_allowlist_rule" "example" {
  depends_on = [scylladbcloud_cluster.test_cluster]
  cluster_id = scylladbcloud_cluster.test_cluster.id
  cidr_block = "${chomp(data.http.myip.response_body)}/32"
}

output "scylladbcloud_allowlist_rule_id" {
  value = scylladbcloud_allowlist_rule.example.rule_id
}

# Fetch credential information for cluster
data "scylladbcloud_cql_auth" "cql_auth" {
  depends_on = [scylladbcloud_cluster.test_cluster]
  cluster_id = scylladbcloud_cluster.test_cluster.id
}

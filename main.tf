terraform {
  required_providers {
    scylladbcloud = {
      source = "scylladb/scylladbcloud"
      version = "1.8.1"
    }
  }
}

resource "random_integer" "offset1" {
  min     = 10
  max     = 250
  keepers = {
    cluster_name = var.scylla_cluster_name
  }
}

resource "random_integer" "offset2" {
  min     = 1
  max     = 250
  keepers = {
    cluster_name = var.scylla_cluster_name
  }
}

locals {
  offset1 = random_integer.offset1.result
  offset2 = random_integer.offset2.result

  scylla_cidr = "10.${local.offset1}.${local.offset2}.0/24"
  loader_cidr = "10.${local.offset1}.${local.offset2 + 1}.0/24"
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
  cidr_block         = local.scylla_cidr
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

# Create Loader VPC
resource "aws_vpc" "loader_vpc" {
  cidr_block           = local.loader_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = {
    Name = "${var.scylla_cluster_name}-vpc"
  }
}

resource "aws_internet_gateway" "loader_igw" {
  vpc_id = aws_vpc.loader_vpc.id

  tags = {
    Name = "${var.scylla_cluster_name}-igw"
  }
}

resource "scylladbcloud_vpc_peering" "sc_peering" {
  cluster_id = scylladbcloud_cluster.sc_cluster.id
  datacenter = scylladbcloud_cluster.sc_cluster.datacenter
  peer_vpc_id      = aws_vpc.loader_vpc.id
  peer_cidr_blocks = [aws_vpc.loader_vpc.cidr_block]
  peer_region      = var.loader_vpc_region
  peer_account_id  = data.aws_caller_identity.current.account_id

  allow_cql = true
}

resource "aws_vpc_peering_connection_accepter" "app" {
    vpc_peering_connection_id = scylladbcloud_vpc_peering.sc_peering.connection_id
    auto_accept               = true
}

# Create a route table for the loader VPC
resource "aws_route_table" "loader_rt" {
  vpc_id = aws_vpc.loader_vpc.id

  tags = {
    Name = "${var.scylla_cluster_name}-route-table"
  }
}

resource "aws_route" "peering_route" {
  route_table_id            = aws_route_table.loader_rt.id
  destination_cidr_block    = local.scylla_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection_accepter.app.vpc_peering_connection_id
}

resource "aws_route" "internet_access" {
  route_table_id         = aws_route_table.loader_rt.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.loader_igw.id
}

# Get available AZs
data "aws_availability_zones" "available" {
  state = "available"
}

# Create 3 subnets in the loader VPC, one per AZ
resource "aws_subnet" "loader_subnets" {
  count                   = 3
  vpc_id                  = aws_vpc.loader_vpc.id
  cidr_block              = cidrsubnet(local.loader_cidr, 4, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.scylla_cluster_name}-subnet-${count.index + 1}"
  }
}

resource "aws_route_table_association" "loader_rta" {
  count          = 3
  subnet_id      = aws_subnet.loader_subnets[count.index].id
  route_table_id = aws_route_table.loader_rt.id
}

output "loader_vpc_id" {
  value = aws_vpc.loader_vpc.id
}
output "loader_route_table_id" {
  value = aws_route_table.loader_rt.id
}
output "loader_subnet_ids" {
  value = aws_subnet.loader_subnets[*].id
}
output "loader_internet_gateway_id" {
  value = aws_internet_gateway.loader_igw.id
}

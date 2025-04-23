variable "scylla_api_token" {
  description = "Scylla Cloud API Token"
  type        = string
  sensitive   = true
}

variable "scylla_cluster_name" {
  type = string
  default = "faisal-migration-source"
  description = "Cluster name on AWS ScyllaDB Cloud"
}

variable "region" {
  type = string
  default = "ap-southeast-1"
  description = "AWS region to use for deployment"
}

variable "node_type" {
  type = string
  default = "t3.micro"
  description = "Nodes type to deploy on AWS"
}

variable "scylla_version" {
  type = string
  default = "2024.1.16"
  description = "ScyllaDB version to deploy"
}

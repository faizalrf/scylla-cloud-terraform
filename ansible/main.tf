provider "aws" {
  region = var.loader_vpc_region
}

data "aws_ami" "scylla_ami" {
  most_recent = true
  owners      = ["158855661827"]

  filter {
    name   = "name"
    values = ["ScyllaDB* ${var.scylla_version}"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

resource "aws_security_group" "loader_sg" {
  name        = "loader-sg"
  description = "Allow outbound CQL and shard-aware access to Scylla Cloud"
  vpc_id      = var.loader_vpc

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 9042
    to_port     = 9042
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 19042
    to_port     = 19142
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_subnets" "loader_subnets" {
  filter {
    name   = "vpc-id"
    values = [var.loader_vpc]
  }
}

resource "aws_key_pair" "loader_key" {
  key_name   = "my-loader-key"
  public_key = file(var.path_to_key)
}

resource "aws_instance" "loader" {
  count                         = var.loaders
  ami                           = data.aws_ami.scylla_ami.id
  instance_type                 = var.loaders_type
  associate_public_ip_address   = true
  subnet_id                     = element(data.aws_subnets.loader_subnets.ids, count.index)
  vpc_security_group_ids        = [aws_security_group.loader_sg.id]
  key_name                      = aws_key_pair.loader_key.key_name

  tags = {
    Name    = "loader-${count.index + 1}"
    Type    = "Loader"
    Region  = var.loader_vpc_region
  }
}

output "loader_instance_names" {
  description = "Names of the loader instances"
  value       = [for instance in aws_instance.loader : instance.tags["Name"]]
}

output "loader_public_ips" {
  description = "Public IP addresses of the loader nodes"
  value       = [for instance in aws_instance.loader : instance.public_ip]
}

output "loader_private_ips" {
  description = "Private IP addresses of the loader nodes"
  value       = [for instance in aws_instance.loader : instance.private_ip]
}

#!/bin/bash
# Safer shell scripting: exit on error, unset vars, error in pipe
set -euo pipefail

# Get absolute path to the script's directory
mydir=$(cd "$(dirname "$0")" && pwd)

# Setup: generate tfvars and provision infrastructure with Terraform and Ansible
function run_setup() {
    echo "Running setup: generating tfvars, provisioning infrastructure..."
    python generate_tfvars.py
    terraform init
    terraform apply --auto-approve

    cd ansible
    terraform init
    terraform apply --auto-approve
    echo "Waiting for 60 seconds for the cluster to stabilize..."
    sleep 60
    python generate_loader_nodes_scripts.py
    echo "Installing cassandra-stress on loader nodes..."
    ansible-playbook install_loader.yml --inventory inventory.ini
    cd "$mydir"
}

# Initialize loader nodes using Ansible
function run_initload() {
    echo "Initializing loader nodes..."
    cd ansible
    python generate_loader_nodes_scripts.py
    ansible-playbook init_load_generator.yml --inventory inventory.ini
    cd "$mydir"
}

# Start stress test jobs
function run_stresstest() {
    echo "Starting stress test..."
    cd ansible
    python generate_loader_nodes_scripts.py
    ansible-playbook kill_cassandra_stress_jobs.yml --inventory inventory.ini
    cd "$mydir"
}

# Scale out the cluster
function run_scaleout() {
    echo "Scaling out cluster..."
    python scale.py --scaleout
}

# Scale in the cluster
function run_scalein() {
    echo "Scaling in cluster..."
    python scale.py --scalein
}

# Destroy all infrastructure
function run_destroy() {
    echo "Destroying infrastructure..."
    terraform destroy --auto-approve
    cd ansible
    terraform destroy --auto-approve
    rm -rf virtual*
    cd "$mydir"
}

# Command dispatcher using case
case "${1:-}" in
    setup) run_setup ;;
    initload) run_initload ;;
    stresstest) run_stresstest ;;
    scaleout) run_scaleout ;;
    scalein) run_scalein ;;
    destroy) run_destroy ;;
    *)
        echo "Usage: $0 {setup|initload|stresstest|scaleout|scalein|destroy}"
        exit 1
        ;;
esac

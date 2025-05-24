#!/bin/bash
# Safer shell scripting: exit on error, unset vars, error in pipe
set -euo pipefail

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Get absolute path to the script's directory
mydir=$(cd "$(dirname "$0")" && pwd)

# Parse arguments
if [[ $# -lt 2 ]]; then
  echo "Usage: $0 {setup|initload|stresstest|scaleout|scalein|destroy} <cluster-id>"
  exit 1
fi

command="$1"
cluster_id="$2"

# Define cluster-specific directories
cluster_dir="${mydir}/clusters/${cluster_id}"
tf_dir="${cluster_dir}/terraform"
tf_ans_dir="${cluster_dir}/ansible"
yaml_file="variables.yml"


box_print() {
    local text_to_print="$1"
    
    horizontal_line="-"
    vertical_line="|"
    top_left="+"
    top_right="+"
    bottom_left="+"
    bottom_right="+"

    # Calculate the length of the text and the print line
    result_length=${#text_to_print}
    total_width=$((result_length + 2))  # Add 2 for the spaces before and after the text
    print_line=$(printf "%-${total_width}s" "" | tr ' ' "${horizontal_line}")

    # Print the box
    echo -e "${top_left}${print_line}${top_right}"
    echo -e "${vertical_line} ${text_to_print} ${vertical_line}"
    echo -e "${bottom_left}${print_line}${bottom_right}"

    # Optional sleep for a brief pause
    #sleep 1
}

# Check if the Cluster we are trying to access is ready!
is_cluster_defined() {
    cluster="$1"

    # Check if the cluster ID exists in the variables.yml
    if ! grep -qE "^[[:space:]]*${cluster}:[[:space:]]*$" "${yaml_file}"; then
        box_print "Cluster '${cluster}' not defined in ${yaml_file}. Please define it before proceeding."
        exit 1
    fi
}

is_cluster_provisioned() {
    cluster="$1"
    if [ ! -f ${tf_dir}/main.tf ]; then
        box_print "Cluster '${cluster}' is not provisioned, please run setup."
        exit 1
    fi
    if [ ! -f ${tf_ans_dir}/main.tf ]; then
        box_print "Cluster '${cluster}' is not provisioned, please run setup."
        exit 1
    fi

}

function run_test() {
    if [ $1 -eq 1 ]; then
        ver=${scylla_version}
    else
        echo "As an example"
        echo "2025-1 (for GCP)"
        echo "2024.2 (for AWS)"
        read -p "Please key in the Scylla version to search for ${provider} Images: " ver
    fi

    box_print "Fetching the list of ${ver}* Image List from ${provider}"
    echo ""
    if [[ ${provider} == "aws" ]]; then
        AWS_PAGER="" aws ec2 describe-images --filters "Name=name,Values=ScyllaDB* ${ver}*" --query 'Images[*].{Name:Name,ID:ImageId}' --region us-east-1 --output text
        ret=$?
    elif [[ ${provider} == "gcp" ]]; then
        gcloud compute images list --project scylla-images --filter="(name~'scylladb-enterprise-${ver}.*' OR name~'scylladb-${ver}.*')" --format="table(name, selfLink)"
        ret=$?
    else
        echo "provider provided not known!"
    fi
    echo ""
    # Check if the command was successful
    if [ ${ret} -eq 0 ]; then
        box_print "The ${provider} connectivity test was successful."
    else
        box_print "The ${provider} connectivity test was unsuccessful!"
    fi
}

sync_files() {
    # Create cluster terraform directory if not exists
    mkdir -p "${tf_dir}"
    box_print "Copying terraform templates to ${tf_dir}"
    cp -r "${mydir}/main.tf"* "${tf_dir}/"
    cp -r "${mydir}/variables.tf"* "${tf_dir}/"

    mkdir -p "${tf_ans_dir}"
    box_print "Copying ansible terraform templates to ${tf_ans_dir}"
    cp ${mydir}/ansible/*.* "${tf_ans_dir}/"
}

# Setup: generate tfvars and provision infrastructure with Terraform and Ansible
function run_setup() {
    echo "Running setup for cluster '${cluster_id}'..."
    sync_files

    echo "Generating tfvars for ${cluster_id}..."
    python generate_tfvars.py --cluster "${cluster_id}"

    box_print "Running Scylla Cloud provisioning..."
    cd "${tf_dir}"
    terraform init
    terraform apply --auto-approve
    cd "${mydir}"
    run_loader_setup
}

function run_loader_setup() {
    is_cluster_provisioned ${cluster_id}
    sync_files
    cd "${tf_ans_dir}"
    box_print "Running Scylla Loaders provisioning..." 
    terraform init
    terraform apply --auto-approve
    box_print "Waiting for 60 seconds for the cluster to stabilize..."
    sleep 60
    python generate_loader_nodes_scripts.py --cluster "${cluster_id}"
    box_print "Installing cassandra-stress on loader nodes..."
    ansible-playbook install_loader.yml --inventory inventory.ini -e "cluster_id=${cluster_id}"
    cd "${mydir}"
}
# Fetch cluster status from SC API
function run_status() {
    is_cluster_provisioned ${cluster_id}
    cd "${mydir}"
    python get_details.py --cluster "${cluster_id}"
}

# Fetch cluster status from SC API
function run_progress_status() {
    is_cluster_provisioned ${cluster_id}
    cd "${mydir}"
    python get_details.py --cluster "${cluster_id}" --progress
}

function run_cloud_status() {
    cd "${mydir}"
    box_print "Checking Scylla Cloud status..."
    python get_cloud_status.py
    cd "${mydir}"
}

# Initialize loader nodes using Ansible
function run_initload() {
    is_cluster_provisioned ${cluster_id}
    sync_files
    box_print "Initializing loader nodes..."
    cd "${tf_ans_dir}"
    python generate_loader_nodes_scripts.py --cluster "${cluster_id}"
    ansible-playbook transfer_loader_scripts.yml --inventory inventory.ini -e "cluster_id=${cluster_id}"
    run_kilload
    ansible-playbook init_load_generator.yml --inventory inventory.ini -e "cluster_id=${cluster_id}"
    cd "${mydir}"
}

# Start stress test jobs
function run_stresstest() {
    is_cluster_provisioned ${cluster_id}
    sync_files
    box_print "Starting stress test..."
    cd "${tf_ans_dir}"
    python generate_loader_nodes_scripts.py --cluster "${cluster_id}"
    ansible-playbook transfer_loader_scripts.yml --inventory inventory.ini -e "cluster_id=${cluster_id}"
    run_kilload
    ansible-playbook stresstest_runner.yml --inventory inventory.ini -e "cluster_id=${cluster_id}"
    cd "${mydir}"
}

# Start stress test jobs
function run_kilload() {
    is_cluster_provisioned ${cluster_id}
    current_dir="${PWD}"
    box_print "Killing Stresss Jobs..."
    cd "${tf_ans_dir}"
    ansible-playbook kill_cassandra_stress_jobs.yml --inventory inventory.ini -e "cluster_id=${cluster_id}"
    cd "${current_dir}"
}

# Scale out the cluster
function run_scaleout() {
    is_cluster_provisioned ${cluster_id}
    box_print "Scaling out cluster '${cluster_id}'..."
    python scale.py --cluster "${cluster_id}" --out
}

# Scale in the cluster
function run_scalein() {
    is_cluster_provisioned ${cluster_id}
    box_print "Scaling in cluster '${cluster_id}'..."
    python scale.py --cluster "${cluster_id}" --in
}

# Destroy all infrastructure
function run_destroy() {
    is_cluster_provisioned ${cluster_id}
    box_print "Destroying Scylla Loaders '${cluster_id}'..."
    cd "${tf_ans_dir}"
    terraform destroy --auto-approve
    box_print "Destroying Scylla Cloud Cluster '${cluster_id}'..."
    cd "${tf_dir}"
    terraform destroy --auto-approve
    box_print "Cleaning up cluster directory: ${cluster_dir}"
    rm -rf "${cluster_dir}"
    cd "${mydir}"
}

if [[ $# -eq 2 ]]; then
    operation="$1"
    cluster="$2"
    is_cluster_defined ${cluster}

    # Auto-detect provider from variables.yml
    result=$(python get_provider.py --cluster ${cluster})
    IFS=':' read -r provider scylla_version <<< "$result"
    if [[ -z "${provider}" ]]; then
        box_print "Error: Could not determine provider for cluster '${cluster}'"
        exit 1
    fi
fi

# Command dispatcher
case "$command" in
    autotest) run_test 1 ;;
    setup) run_setup ;;
    loader_setup) run_loader_setup ;;
    status) run_status ;;
    cloudstatus) run_cloud_status ;;
    progress) run_progress_status ;;
    initload) run_initload ;;
    stresstest) run_stresstest ;;
    kilload) run_kilload ;;
    scaleout) run_scaleout ;;
    scalein) run_scalein ;;
    destroy) run_destroy ;;
    *)
        echo "Usage: $0 {setup|initload|stresstest|scaleout|scalein|destroy} --cluster-id <id>"
        exit 1
        ;;
esac

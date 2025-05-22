import string
import yaml
import os
import shutil
import math
import paramiko
import subprocess
import json
import argparse
from paramiko import RSAKey, Ed25519Key
from collections import defaultdict
from google.cloud import compute_v1

#To handle loading of both RSA and ED25519 keys
def load_ssh_key(key_path):
    key_path = os.path.expanduser(key_path)
    key = None
    try:
        key = RSAKey.from_private_key_file(key_path)
    except Exception:
        try:
            key = Ed25519Key.from_private_key_file(key_path)
        except Exception as e:
            print(f"Failed to load SSH key at {key_path}: {e}")
    return key

def estimate_row_size(template):
    """
    Estimate the average row size from a Cassandra stress profile template.

    Args:
        template (dict): The stress profile template as a dictionary.

    Returns:
        int: Estimated average row size in bytes.
    """
    # Map data types to their default sizes
    data_type_sizes = {
        'uuid': 16,  # UUID is 16 bytes
        'text': 50,  # Default size for text if no size specified
        'blob': 128  # Default size for blob if no size specified
    }

    estimated_size = 0  # Initialize row size

    for column in template['columnspec']:
        column_type = None
        column_size = 0

        # Infer data type from column name or default to text
        if 'name' in column:
            column_name = column['name']
            if column_name == 'id':
                column_type = 'uuid'
            elif column_name == 'value':
                column_type = 'blob'  # Special handling for BLOB
            else:
                column_type = 'text'

        # Handle column sizes based on the 'size' parameter
        if 'size' in column:
            size_range = column['size']
            
            # Fixed size
            if 'fixed' in size_range:
                size = int(size_range.replace('fixed(', '').replace(')', ''))
                column_size = size

            # Gaussian size
            elif 'gaussian' in size_range:
                sizes = size_range.replace('gaussian(', '').replace(')', '').split('..')
                min_size = int(sizes[0])
                max_size = int(sizes[1])
                column_size = round((min_size + max_size) / 2)  # Average size

            # Sequential size
            elif 'sequential' in size_range:
                sizes = size_range.replace('sequential(', '').replace(')', '').split('..')
                min_size = int(sizes[0])
                max_size = int(sizes[1])
                column_size = round((min_size + max_size) / 2)  # Average size

        # Use predefined sizes for data types
        elif column_type in data_type_sizes:
            column_size = data_type_sizes[column_type]

        # Add column overhead (Cassandra internal metadata)
        estimated_size += (column_size)

        print(f"Column: {column.get('name', 'unknown')}, Type: {column_type}, Size: {column_size} bytes")

    # Add general row overhead and multiply for scaling
    # row_overhead_multiplier = 2  # Approximation for row metadata overhead
    # estimated_size *= row_overhead_multiplier

    return estimated_size
    
def load_template(file_path):
    with open(file_path, 'r') as file:
        template = yaml.safe_load(file)
    return template

# Clear the stress_inventory directory before proceeding
def clear_stress_inventory(stress_inventory_dir):
    # Only delete subdirectories that start with "virtual"
    if os.path.exists(stress_inventory_dir):
        for entry in os.listdir(stress_inventory_dir):
            entry_path = os.path.join(stress_inventory_dir, entry)
            if os.path.isdir(entry_path) and entry.startswith("virtual"):
                shutil.rmtree(entry_path)

def is_scylla_running(public_ip, config):
    try:
        username='ubuntu'
        key_path=config['path_to_private']
        key = load_ssh_key(key_path)
        if key is None:
            return False
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(public_ip, username=username, pkey=key, timeout=5)

        stdin, stdout, stderr = ssh.exec_command("pgrep -x scylla")
        result = stdout.read().decode().strip()
        ssh.close()

        return bool(result)
    except Exception as e:
        print(f"Error connecting to {public_ip}: {e}")
        return False

# Function to get nodes by tags and cluster name, and ensure they are running
def get_nodes_by_tag_and_cluster_aws(session, config, cluster_name, tag_key, tag_value, group_values, region):
    ec2 = session.resource('ec2', region_name=region)
    filters = [
        {'Name': f'tag:{tag_key}', 'Values': [tag_value]},
        {'Name': 'tag:Project', 'Values': [cluster_name]},  # Filter based on the project name (cluster name)
        {'Name': 'instance-state-name', 'Values': ['running']},  # Ensure only running instances are fetched
    ]
    cluster_prefix = f"{cluster_name}".lower()

    if group_values:
        filters.append({'Name': 'tag:Group', 'Values': group_values})  # Apply Group filter if provided
    
    instances_list = []
    instances = ec2.instances.filter(Filters=filters)

    for instance in instances:
        instance_name = next((tag['Value'] for tag in instance.tags or [] if tag['Key'] == 'Name'), '').lower()
        instance_type = next((tag['Value'] for tag in instance.tags or [] if tag['Key'] == 'Type'), '')

        if not instance_name.startswith(cluster_prefix):
            continue

        if instance_type == "Scylla":
            if not is_scylla_running(instance.public_ip_address, config):
                continue

        instances_list.append(instance)

    #instances_list = list(instances)  # Convert to list to iterate and print
    print(f"Found {len(instances_list)} instances with tag {tag_key}={tag_value} in region {region} and group {group_values}")
    
    return instances_list

def get_nodes_by_tag_and_cluster_gcp(compute_client, config, tag_key, tag_value, group_values):
    from google.cloud.compute_v1.types import AggregatedListInstancesRequest

    instance_list = []
    cluster_name = config['cluster_name']
    project_id = config['gcp_project_id']
    cluster_prefix = f"{cluster_name}".lower()

    request = AggregatedListInstancesRequest(project=project_id)
    agg_list = compute_client.aggregated_list(request=request)

    for region in config['regions']:
        for zone, scoped_list in agg_list:
            if not scoped_list.instances:
                continue
            
            if not str(zone).startswith(f"zones/{region}"):
                continue

            for instance in scoped_list.instances:
                public_ip = None
                if not instance.name.lower().startswith(cluster_prefix):
                    continue

                if instance.network_interfaces and instance.network_interfaces[0].access_configs:
                    public_ip = instance.network_interfaces[0].access_configs[0].nat_i_p

                if instance.status != "RUNNING":
                    continue

                # Check if type is Scylla and verify if the scylla process is running
                labels = instance.labels or {}
                instance_type = labels.get("type", "").lower()
                if instance_type == "scylla":
                    if not is_scylla_running(public_ip, config):
                        continue

                tag_match = labels.get(tag_key.lower()) == tag_value.lower()
                group_match = not group_values or labels.get("group", "").lower() in [g.lower() for g in group_values]

                if tag_match and group_match:
                    instance_list.append(instance)

        print(f"Found {len(instance_list)} instances in region {region} matching tag {tag_key}={tag_value} and group {group_values}")

    return instance_list

# Function to extract relevant information from instances
def get_instance_info_aws(instance):
    return {
        'id': instance.id,
        'name': next((tag['Value'] for tag in instance.tags if tag['Key'] == 'Name'), 'Unnamed'),
        'private_ip': instance.private_ip_address,
        'public_ip': instance.public_ip_address if instance.public_ip_address else None,  # Handle missing public IP
        'zone': instance.placement['AvailabilityZone']  # Use full Availability Zone
    }

def get_instance_info_gcp(instance):
    # Extract primary network interface
    network_interface = instance.network_interfaces[0] if instance.network_interfaces else None
    private_ip = network_interface.network_i_p if network_interface else None

    # Extract public (external) IP if it exists
    access_configs = network_interface.access_configs if network_interface and network_interface.access_configs else []
    public_ip = access_configs[0].nat_i_p if access_configs else None

    return {
        'id': instance.id,
        'name': instance.name,
        'private_ip': private_ip,
        'public_ip': public_ip,
        'zone': instance.zone.split('/')[-1]  # Extract "us-east1-b" from full path
    }

def generate_stress_profiles(data_dump, template_file_path):
    for data in data_dump:
        output_directory = f"./{data['loader_zone']}/{data['loader_name']}"  # Directory to save the generated scripts

        # Ensure the output directory exists
        os.makedirs(output_directory, exist_ok=True)
        # Open the file as for string manipulation
        with open(template_file_path, 'r') as file:
            template_content = file.read()

        # Extract the keyspace_definition from the template
        keyspace_definition_start = "keyspace_definition: |"
        keyspace_start = None
        lines = template_content.splitlines()

        for i, line in enumerate(lines):
            if line.strip().startswith(keyspace_definition_start):
                keyspace_start = lines[i + 1].strip()
                break

        if keyspace_start:
            # Modify the keyspace creation statement based on the tablets_enabled flag in data
            if data['tablets_enabled']:
                keyspace_modified = f"{keyspace_start[:-1]} AND tablets = {{'enabled': true, 'initial': 128}};"
            else:
                keyspace_modified = keyspace_start
            
            # Replace the original keyspace definition in the template content
            template_content = template_content.replace(keyspace_start, keyspace_modified)

        # Create a Template object
        template = string.Template(template_content)

        # Replace the start and end population numbers with the values calculated
        script_content = template.safe_substitute(start=data['population_start'], end=data['population_end'])
        suffix = "main"
        script_filename = f"{data['stress_profile_name']}_{data['loader_name']}_i{data['profile_instance']}_{suffix}.yaml"
        script_filepath = os.path.join(output_directory, script_filename)
        
        with open(script_filepath, 'w') as script_file:
            script_file.write(script_content)

        generate_loader_scripts(data, output_directory, script_filename, suffix)
        generate_stresstest_scripts(data, output_directory, script_filename, suffix)

def generate_loader_scripts(data, output_directory, yaml_script_filename, suffix):
    # Generate the shell scripts
    profile_instance = data['profile_instance']
    script_filename = f"loader_{profile_instance}_{suffix}.sh"

    script_filepath = os.path.join(output_directory, script_filename)

    with open(script_filepath, 'w') as script_file:
        log_file = f'scylla_loader_{profile_instance + 1}_$(date "+%Y-%m-%d_%H%M%S").log'
        script_file.write(f"#!/bin/bash\n\n")
        script_file.write(f"log_file=\"{log_file}\"\n\n"
                            f"timeout=60  # Maximum wait time in seconds\n"
                            f"interval=2  # Interval between checks in seconds\n"
                            f"elapsed=0\n\n")
        
        population_steps = data['population_steps']
        scylla_private_ip = data['scylla_private_ip']
        consistency_level = data['consistency_level']
        throttle = math.trunc(data['loader_throttle'] / ((data['loader_node_count']) * data['loader_processes']))  # Per loader trottling. If 150k total throttle, 3 loaders will be 150k/3=50k per node
        threads = math.trunc(data['loader_threads'] / ((data['loader_node_count']) * data['loader_processes']))  # Per loader threads. If 300 total threads, 3 loaders will be 150/3=50 per node
        #Disable throttling if ZERO
        if data['loader_throttle'] > 0: 
            loader_throttle=f"throttle={throttle}/s"
        else: 
            loader_throttle=""
        
        scylla_private_ip_str = ",".join(data['scylla_private_ip_list'])
        user = data['scylla_cql_username']
        password = data['scylla_cql_password']
        script_text = f"nohup cassandra-stress user profile={yaml_script_filename} cl={consistency_level} no-warmup n={population_steps} "\
                        f"'ops(insert=1)' -mode native cql3 user={user} password={password} -rate threads={threads} {loader_throttle} "\
                        f"-log interval=5 -node {scylla_private_ip_str}> cassandra-stress-stresser.out 2>&1 &\n"
        
        script_file.write(script_text)

        script_file.write(f"chmod 750 loader_log_{data['profile_instance'] + 1}.sh\n")
        
        #print(f"Loader script generated: {script_filepath}")

def generate_stresstest_scripts(data, output_directory, yaml_script_filename, suffix):
    # Generate the shell scripts
    profile_instance = data['profile_instance']
    script_filename = f"stresstest_{profile_instance}_{suffix}.sh"

    script_filepath = os.path.join(output_directory, script_filename)
    
    # Split the read/write stresstest ratio
    writes, reads = map(int, data['stress_ratio'].split(':'))
    
    stress_query = data['stress_query']
    stress_duration = data['stress_duration']
    consistency_level = data['consistency_level']

    with open(script_filepath, 'w') as script_file:
        log_file = f"stresstest_{profile_instance + 1}_$(date \"+%Y-%m-%d_%H%M%S\").log"
        script_file.write(f"#!/bin/bash\n\n")
        script_file.write(f"log_file=\"{log_file}\"\n\n"
                            f"timeout=60  # Maximum wait time in seconds\n"
                            f"interval=2  # Interval between checks in seconds\n"
                            f"elapsed=0\n\n")

        throttle = math.trunc(data['stress_throttle'] / ((data['loader_node_count']) * data['stress_processes']))  # Per loader trottling. If 150k total throttle, 3 nodes will be 150k/3=50k per node
        threads = math.trunc(data['stress_threads'] / ((data['loader_node_count']) * data['stress_processes']))  # Per loader threads. If 150 total threads, 3 nodes will be 150/3=50 per node

        #Disable throttling if ZERO
        if data['stress_throttle'] > 0: 
            stress_throttle=f"throttle={throttle}/s"
        else: 
            stress_throttle=""
        
        scylla_private_ip_str = ",".join(data['scylla_private_ip_list'])
        user = data['scylla_cql_username']
        password = data['scylla_cql_password']

        script_text = f"nohup cassandra-stress user profile={yaml_script_filename} cl={consistency_level} no-warmup duration={stress_duration} "\
                        f"'ops(insert={writes},{stress_query}={reads})' -mode native cql3 user={user} password={password} -rate threads={threads} {stress_throttle} "\
                        f"-log interval=5 -node {scylla_private_ip_str}> cassandra-stress-stresser.out 2>&1 &\n\n"
        
        script_file.write(script_text)

        script_file.write(f"chmod 750 stress_log_{profile_instance + 1}.sh\n")

def generate_inventory():
    output = subprocess.check_output(["terraform", "output", "-json"])
    tf_output = json.loads(output)

    private_ips = tf_output["loader_private_ips"]["value"]
    public_ips = tf_output["loader_public_ips"]["value"]
    instance_names = tf_output["loader_instance_names"]["value"]

    with open("inventory.ini", "w") as f:
        f.write("[loaders]\n")
        for name, ip, pub_ip in zip(instance_names, private_ips, public_ips):
            f.write(f"{ip} ansible_host={pub_ip} ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_ed25519\n")

        f.write("\n[loaders:vars]\n")
        f.write("ansible_python_interpreter=/usr/bin/python3\n")

def main(config):
    # --- Fetch scylla_nodes and CQL credentials using Terraform output for cluster_id ---
    region_name = next(iter(config['regions']))

    # Fetch cluster_id and CQL credentials from Terraform output in parent dir
    tf_output = json.loads(subprocess.check_output(["terraform", "output", "-json"], cwd="../terraform"))
    # Extract CQL user credentials from Terraform output
    scylla_cql_username = tf_output["scylla_cql_username"]["value"]
    scylla_cql_password = tf_output["scylla_cql_password"]["value"]
    scylla_private_ips = tf_output["scylla_private_ips"]["value"]
    scylla_nodes = [{"private_ip": ip} for ip in scylla_private_ips]

    # --- Fetch loader_nodes from Terraform output ---
    tf_output = json.loads(subprocess.check_output(["terraform", "output", "-json"], cwd="./"))
    loader_names = tf_output["loader_instance_names"]["value"]
    loader_private_ips = tf_output["loader_private_ips"]["value"]
    loader_public_ips = tf_output["loader_public_ips"]["value"]

    loader_nodes = [{
        'name': name,
        'private_ip': priv_ip,
        'public_ip': pub_ip,
        'zone': "virtual-1a"
    } for name, priv_ip, pub_ip in zip(loader_names, loader_private_ips, loader_public_ips)]

    region_name = next(iter(config["regions"]))
    region = config["regions"][region_name]
    loader_node_count = region["loaders"]
    scylla_node_count = region["nodes"]

    startPopulation = 0
    num_loader_instances = config['stress_setup']['number_of_loader_instances']  # Number of initial data loading processes per Loader node
    num_stress_instances = config['stress_setup']['number_of_stress_instances']  # Number of stress testing processes per Loader node

    # Open the keyspace template processing and generating new scripts
    stress_profile_name = config['stress_setup'].get('stress_profile_name', "unknown")
    template_file_path = f"./{stress_profile_name}.yaml.tp"

    if not os.path.isfile(template_file_path):
        print(f"Error: Stress profile template file '{template_file_path}' does not exist.")
        exit(1)
    print(f"Stress profile template file '{template_file_path}' is selected")
    template = load_template(template_file_path)

    # Calculate Steps here instead of reading from the config
    OneTB = (1024**4)
    estimated_row_size = (estimate_row_size(template))
    if estimated_row_size <= 0:
        estimated_row_size = 1

    desired_cluster_size = config['stress_setup']['desired_cluster_size'] # Per loader node process
    desired_row_count = config['stress_setup']['desired_row_count']
    total_cluster_size = desired_cluster_size * OneTB  # This calculates the total cluster size across the entire cluster (not per node)
    total_loader_instances_on_cluster = loader_node_count * max(num_loader_instances, num_stress_instances)
    if total_loader_instances_on_cluster <= 0:
        total_loader_instances_on_cluster = 1

    # If desired_row_count is greater than 0 then the desired_cluster_size is ignored 
    if desired_row_count > 0:
        total_cluster_rows = desired_row_count
    else:
        total_cluster_rows = math.trunc(total_cluster_size / estimated_row_size)

    output_str=f"{desired_cluster_size}TiB Cluster Size with {total_cluster_rows:,} rows"

    population_step = total_cluster_rows // total_loader_instances_on_cluster

    # Calculate total logical rows
    total_cluster_rows = desired_row_count if desired_row_count > 0 else math.trunc(total_cluster_size / estimated_row_size)
    population_step = total_cluster_rows // total_loader_instances_on_cluster

    print (f"Number of Loaders {loader_node_count}, Instances {num_loader_instances}, Estimated Row Size {estimated_row_size}b, Total Cluster Size {output_str}, Estimated Rows needed per Loader instance {population_step:,}")
    population_steps = population_step
    endPopulation = population_step

    # Clear the stress_inventory directory/fies at the start of the script
    clear_stress_inventory(f"./")

    # Path to your inventory and directory, this inventory is to transfer all the generated files to the loaders appropriate loader nodes
    base_dir = './'
    playbook_file = f'{base_dir}/transfer_loader_scripts.yml'

    # Search and delete all the existing .sh and .yml files on teh remote hosts before copy the new ones. Faisal, 2024-08-24
    with open(playbook_file, 'w') as pb_file:
        pb_file.write("---\n"
                        "- name: Transfer files to all loader hosts\n"
                        "  hosts: loaders\n"
                        "  gather_facts: no\n"
                        "  tasks:\n"
                        "    - name: Find all .sh and .yaml files in the home directory\n"
                        "      ansible.builtin.find:\n"
                        "        paths: /home/ubuntu/\n"
                        "        recurse: no\n"
                        "        patterns:\n"
                        "          - '*.sh'\n"
                        "          - '*.yaml'\n"
                        "      register: files_to_delete\n"
                        "      no_log: true\n"
                        "    - name: Delete all .sh and .yaml files\n"
                        "      ansible.builtin.file:\n"
                        "        path: '{{ item.path }}'\n"
                        "        state: absent\n"
                        "      loop: '{{ files_to_delete.files }}'\n"
                        "      when: files_to_delete.matched > 0\n"
                        "      no_log: true\n"
                        "    - name: Copy files to each loader\n"
                        "      copy:\n"
                        "        src: '{{ playbook_dir }}/{{ item.src_folder }}/'\n"
                        "        dest: /home/ubuntu/\n"
                        "        owner: ubuntu\n"
                        "        group: ubuntu\n"
                        "        mode: '0755'\n"
                        "      no_log: true\n"
                        "      loop:\n")  # Write this only once

    print(f"IP Distribution Strategy Selected '1:1 loader to scylla mapping'")

    # 1:1 loader-to-scylla mapping, round robin if counts differ.
    for i, loader in enumerate(loader_nodes):
        data_dump = []
        print(f"Zone: {loader['zone']} - Loader Node: {loader['name']}")

        # Map each loader to a single Scylla node, round robin
        scylla = scylla_nodes[i % len(scylla_nodes)]
        profile_instance = 0
        max_number_of_instances = max(num_loader_instances, num_stress_instances)
        for instance_index in range(max_number_of_instances):
            print(f"  - Population Range for {loader['name']} instance {instance_index + 1}: Start: {startPopulation:,}, End: {endPopulation:,}")
            data_dump.append({
                'loader_zone': loader['zone'],
                'loader_name': loader['name'],
                'loader_private_ip': loader['private_ip'],
                'loader_public_ip': loader['public_ip'],
                'scylla_private_ip': scylla['private_ip'],
                'scylla_private_ip_list': [scylla['private_ip']],
                'scylla_public_ip': scylla['private_ip'],
                'scylla_node_count': scylla_node_count,
                'scylla_cql_username': scylla_cql_username,
                'scylla_cql_password': scylla_cql_password,
                'stress_profile_name': config['stress_setup']['stress_profile_name'],
                'profile_instance': profile_instance,
                'population_steps': population_steps,
                'desired_cluster_size': config['stress_setup']['desired_cluster_size'],
                'desired_row_count': config['stress_setup']['desired_row_count'],
                'population_start': startPopulation,
                'population_end': endPopulation,
                'loader_node_count': loader_node_count,
                'dummy_loader_count': loader_node_count,
                'loader_threads': config['stress_setup']['number_of_loader_threads'],
                'loader_throttle': config['stress_setup']['loader_throttle'],
                'loader_processes': num_loader_instances,
                'stress_threads': config['stress_setup']['number_of_stress_threads'],
                'stress_processes': num_stress_instances,
                'stress_throttle': config['stress_setup']['stress_throttle'],
                'consistency_level': config['stress_setup']['consistency_level'],
                'stress_duration': config['stress_setup']['stress_duration_minutes'],
                'stress_ratio': config['stress_setup']['ratio'],
                'stress_query': config['stress_setup']['select_query'],
                'tablets_enabled': config['scylla_params']['enable_tablets'],
                'query_to_execute': config['stress_setup']['select_query']
            })
            profile_instance += 1
            startPopulation = endPopulation
            endPopulation += population_step

        generate_stress_profiles(data_dump, template_file_path)

        with open(playbook_file, 'a') as pb_file:
            pb_file.write(f"        - {{ name: '{loader['private_ip']}', src_folder: '{loader['zone']}/{loader['name']}' }}\n")
    with open(playbook_file, 'a') as pb_file:
        pb_file.write(f"      when: inventory_hostname == item.name\n")

    generate_inventory()

def read_config(file_path):
    # Get the path to the current script and go up three levels
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

if __name__ == "__main__":
    # Initialize argument parser
    parser = argparse.ArgumentParser(description="ScyllaDB Cloud Cluster Setup")
    parser.add_argument("--cluster", required=True, help="Cluster ID to configure")

    try:
        # Parse arguments
        args = parser.parse_args()
    except SystemExit:
        print("Error: Missing required argument --cluster")
        print("Usage: python script.py --cluster-id <cluster_id>")
        exit(1)

    # Parse arguments
    args = parser.parse_args()
    cluster_id = args.cluster

    # Load YAML configuration but variables.yml is Far Far Away!!!
    config = read_config("../../../variables.yml")  # Ensure correct path

    # Extract only the 'clusters' dictionary
    clusters = config.get('clusters', {})

    # Get the specific cluster configuration
    cluster_config = clusters.get(cluster_id)

    if not cluster_config:
        print(f"Error: Cluster '{cluster_id}' not found in variables.yml!")
        exit(1)

    # Now `cluster_config` contains only the data for the requested cluster
    print(f"Extracted configuration for cluster '{cluster_id}':")
    main(cluster_config)

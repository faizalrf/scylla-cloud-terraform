import json
import subprocess

# Run terraform output -json and parse it
output = subprocess.check_output(["terraform", "output", "-json"])
tf_output = json.loads(output)

private_ips = tf_output["loader_private_ips"]["value"]
public_ips = tf_output["loader_public_ips"]["value"]
instance_names = tf_output["loader_instance_names"]["value"]

with open("stress_inventory/inventory.ini", "w") as f:
    f.write("[loaders]\n")
    for name, ip, pub_ip in zip(instance_names, private_ips, public_ips):
        f.write(f"{ip} ansible_host={pub_ip} ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_ed25519\n")

    f.write("\n[loaders:vars]\n")
    f.write("ansible_python_interpreter=/usr/bin/python3\n")
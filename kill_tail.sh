#!/bin/bash

cluster_id=$1
BASE_DIR="$(dirname "$0")/clusters/$cluster_id/ansible"
LOADER_IP=$(terraform -chdir="$BASE_DIR" output -json | jq -r '.loader_public_ips.value[0]')

echo "Killing tail -f process on $LOADER_IP..."
ssh -o StrictHostKeyChecking=no scyllaadm@"$LOADER_IP" "pkill -f 'tail -f /home/scyllaadm/cassandra-stress-stresser.out'"
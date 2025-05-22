#!/bin/bash

CLUSTER_ID="tiny-cluster"
BASE_DIR="$(dirname "$0")/clusters/$CLUSTER_ID/ansible"
echo "Base directory: $BASE_DIR"
LOADER_IP=$(terraform -chdir="$BASE_DIR" output -json | jq -r '.loader_public_ips.value[0]')
echo "Tailing log from $LOADER_IP..."
ssh -o StrictHostKeyChecking=no scyllaadm@"$LOADER_IP" 'tail -f /home/scyllaadm/cassandra-stress-stresser.out'

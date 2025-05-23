#!/bin/bash

CLUSTER_ID="$1"

if [ -z "$CLUSTER_ID" ]; then
  echo "Usage: $0 <cluster-id>"
  exit 1
fi

BASE_DIR="$(dirname "$0")/clusters/$CLUSTER_ID/ansible"
LOADER_IP=$(terraform -chdir="$BASE_DIR" output -json | jq -r '.loader_public_ips.value[0]')
echo "$LOADER_IP" > "./current_tail_loader_ip_${CLUSTER_ID}.txt"
ssh -o StrictHostKeyChecking=no scyllaadm@"$LOADER_IP" 'tail -f /home/scyllaadm/cassandra-stress-stresser.out'

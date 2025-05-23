#!/bin/bash

CLUSTER_ID="$1"

if [ -z "$CLUSTER_ID" ]; then
  echo "Usage: $0 <cluster-id>"
  exit 1
fi

BASE_DIR="$(dirname "$0")/clusters/$CLUSTER_ID/ansible"
echo "Base dir: $BASE_DIR"

LOADER_IP=$(cat "./current_tail_loader_ip_${CLUSTER_ID}.txt")
echo "Loader IP: $LOADER_IP"
ssh -o StrictHostKeyChecking=no scyllaadm@"$LOADER_IP" "pkill -f 'tail -f /home/scyllaadm/cassandra-stress-stresser.out'"

if [ $? -eq 0 ]; then
    rm -rf "./current_tail_loader_ip_${CLUSTER_ID}.txt"
else
    echo "Failed to kill tail process."
fi

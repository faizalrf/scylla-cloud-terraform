sudo gpg --homedir /tmp --no-default-keyring --keyring /etc/apt/keyrings/scylladb.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys a43e06657bac99e3
sudo curl -L --output /etc/apt/sources.list.d/scylla.list https://downloads.scylladb.com/deb/ubuntu/scylla-2025.1.list
sudo apt-get update
sudo apt install -y scylla-tools openjdk-17-jdk

# This script installs ScyllaDB tools and runs a Cassandra stress test.


kv.yaml
--------------------
keyspace: keyspace1

keyspace_definition: |
  CREATE KEYSPACE keyspace1 WITH replication = {'class': 'NetworkTopologyStrategy', 'replication_factor': 3} AND tablets = {'enabled': true, 'initial': 128};

# For creating the keyspace on the target cluster, add `AND tablets = {'enabled': true, 'initial': 128}`
table: standard1

table_definition: |
  CREATE TABLE keyspace1.standard1 (
    key blob,
    value blob,
    PRIMARY KEY (key)
  ) WITH compression = {};

columnspec:
  - name: key
    size: fixed(10)
    population: uniform(1..1000000000)
  - name: value
    size: fixed(1024)
    population: uniform(1..100000000)

insert:
  partitions: fixed(1)
  batchtype: UNLOGGED

queries:
  select:
    cql: select * from standard1 where key = ?
    fields: samerow
--------------------


for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do sudo apt-get remove $pkg; done

# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y


nohup cassandra-stress user profile=kv.yaml cl=ONE n=100000000 'ops(insert=1)' \
  no-warmup -mode native cql3 user=scylla password=dcjC24AFLMR1plJ \
  -rate threads=100 \
  -log interval=5 \
  -node 10.20.0.166 > loader_log.out 2>&1 &

./sbin/start-master.sh

./sbin/start-worker.sh -c 14 -m28G spark://ip-10-10-0-5:7077

./bin/spark-submit \
  --class com.scylladb.migrator.Migrator \
  --master spark://ip-10-10-0-5:7077 \
  --conf spark.scylla.config=/home/ubuntu/config_simple.yaml \
  --executor-cores 7 \
  --executor-memory 14G \
  --total-executor-cores 14 \
  /home/ubuntu/scylla-migrator-assembly.jar


source:
  type: scylla
  host: 172.31.0.44
  port: 9042
  localDC: AWS_AP_SOUTHEAST_1
  credentials:
    username: scylla
    password: 2eEabPu43SqfjsQ
  keyspace: keyspace1
  table: standard1
  consistencyLevel: LOCAL_QUORUM
  preserveTimestamps: true
  splitCount: 256
  connections: 128
  fetchSize: 2000
  
target:
  type: scylla
  host: 172.30.0.90
  port: 9042
  localDC: AWS_AP_SOUTHEAST_1
  credentials:
    username: scylla
    password: B4EC3uWfeHd0tyc
  keyspace: keyspace1
  table: standard1
  consistencyLevel: LOCAL_QUORUM
  connections: 256
  stripTrailingZerosForDecimals: false
savepoints:
  path: /home/ubuntu/savepoints
  intervalSeconds: 300

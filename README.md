# Scylla Cloud Automation

This project automates the deployment and benchmarking of ScyllaDB clusters on Scylla Cloud, along with provisioning of loader infrastructure and complete testing workflows.

## Features

- Provision Scylla Cloud clusters using Terraform
- Automatically configure loader infrastructure for stress testing
- Full Ansible integration for provisioning and testing
- Cluster lifecycle operations (setup, scale, destroy)
- Multi-cluster management via a unified `variables.yml`
- CLI and web UI support

## Prerequisites

- Linux (Ubuntu/Rocky/Fedora/MacOS/WSL2)
- Python 3.12.x (3.13+ not supported)
- pip3
- [Terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli)
- [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html#installing-and-upgrading-ansible-with-pipx)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) (configured)
- Scylla Cloud API Token

---

## Setup

### 1. Clone the Repository

```bash
git clone ...
```

### 2. Python Environment

#### OS-specific dependencies

<details>
<summary>Show install commands for your OS</summary>

**Ubuntu/Debian/Mint**

```bash
sudo apt update
sudo apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
libffi-dev liblzma-dev git
```

**Fedora**

```bash
sudo dnf install -y gcc gcc-c++ make zlib-devel bzip2 bzip2-devel \
readline-devel sqlite sqlite-devel openssl-devel xz xz-devel \
libffi-devel findutils tk-devel libuuid-devel libnsl2 git
```

**Rocky/CentOS/RHEL**

```bash
sudo dnf install -y epel-release
sudo dnf install -y gcc gcc-c++ make zlib-devel bzip2 bzip2-devel \
readline-devel sqlite sqlite-devel openssl-devel xz xz-devel \
libffi-devel findutils tk-devel libuuid-devel libnsl2 git
```

**Suse**

```bash
sudo zypper install -y gcc make zlib-devel bzip2 readline-devel \
sqlite3-devel openssl-devel xz xz-devel libffi-devel libnsl-devel \
libuuid-devel libtirpc-devel tk-devel wget git curl
```

**MacOS**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install openssl readline sqlite3 xz zlib bzip2 git
```

</details>

#### All Platforms (Common)

Install pyenv:

```bash
curl https://pyenv.run | bash
```

Run the alias setup script:

```bash
./setup-aliases.sh
source ~/.bashrc  # or source ~/.zshrc etc
```

Check that your shell has the following:

```bash
alias clx="./scylla-automation-framework.sh"
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
alias pyenv-set-312="pyenv activate myenv312"
```

Install Python 3.12.x and create virtualenv:

```bash
pyenv install 3.12.10
pyenv virtualenv 3.12.10 myenv312
pyenv-set-312
```

Check version:

```bash
python --version  # Should be Python 3.12.x
```

Install requirements:

```bash
pip3 install -r requirements.txt
```

---

### 3. Cloud Authentication

#### AWS Authentication

Install [gimme-aws-creds](https://github.com/Nike-Inc/gimme-aws-creds):

```bash
pip3 install --upgrade gimme-aws-creds
```

Configure `~/.okta_aws_login_config` and `~/.aws/credentials` as described below:

<details>
<summary>Show AWS Okta config sample</summary>

```ini
[DEFAULT]
okta_org_url = https://scylladb.okta.com
client_id = 0oab7271m7nRkKmlw5d7
write_aws_creds = True
cred_profile = acc-role
okta_username = <your.name>@scylladb.com
app_url = https://scylladb.okta.com/home/amazon_aws/0oa2uxps59d96E5Cj5d7/272
remember_device = True
preferred_mfa_type = Okta
aws_default_duration = 21600

[cx-cs-lab]
inherits = DEFAULT
aws_rolename = arn:aws:iam::<account>:role/DevOpsAccessRole
cred_profile = DevOpsAccessRole
```

Add dummy credentials to `~/.aws/credentials`:

```ini
[DevOpsAccessRole]
aws_access_key_id = dummy
aws_secret_access_key = dummy
```
</details>

Run:

```bash
export AWS_PROFILE=DevOpsAccessRole
gimme-aws-creds -p cx-cs-lab
```
You may wish to add the export to your `.bashrc`/`.zshrc`.

---

## Directory Structure

```
.
├── clusters/                   # Auto-generated folders for each cluster
│   └── <cluster-id>/
│       ├── terraform/          # Scylla Cloud Terraform code
│       └── ansible/            # Loader provisioning and config
├── ansible/                    # Shared Ansible playbooks and templates
├── generate_tfvars.py          # Converts variables.yml to tfvars
├── generate_loader_nodes_scripts.py  # Generates SSH and workload scripts
├── scale.py                    # Handles scale in/out using Scylla API
├── get_details.py              # Displays current node info in table
├── get_provider.py             # Determines cloud and version
├── scylla-cloud-operations.sh  # Main lifecycle controller
├── tail_loader_log.sh          # Tails cassandra-stress logs from loader
├── kill_tail.sh                # Kills tailing session from GUI
├── variables.yml               # Unified cluster configuration
└── README.md
```

## Usage

### Define Cluster

Edit `variables.yml` and define one or more clusters under `clusters:`.

```yaml
clusters:
  tiny-cluster:
    scylla_api_token: "<your-token>"
    cluster_name: "tiny-cluster"
    ...
```

_**Note:** Important to change the cluster_name to keep it unique between other users._

### Setup

```bash
./scylla-cloud-operations.sh setup tiny-cluster
```

This will:
- Generate tfvars
- Copy templates
- Provision infrastructure on Scylla Cloud and loader VPC
- Peer VPCs

### Loader Setup

```bash
./scylla-cloud-operations.sh loader_setup tiny-cluster
```

### Stress Testing

```bash
./scylla-cloud-operations.sh stresstest tiny-cluster
```

### Kill Load

```bash
./scylla-cloud-operations.sh kilload tiny-cluster
```

### Scale

```bash
./scylla-cloud-operations.sh scaleout tiny-cluster
./scylla-cloud-operations.sh scalein tiny-cluster
```

### Destroy

```bash
./scylla-cloud-operations.sh destroy tiny-cluster
```

## Web UI

A real-time web interface is available via `app.py` (Flask-based). It lets you:

- Manage clusters
- View logs in real time
- Tail cassandra-stress output from Loaders directly on the browser
- Edit `variables.yml` from within the UI

**Launch the app with:**

```bash
python -u app.py
```

### Notes

- CIDRs for Scylla Cloud and Loader VPCs are dynamically generated and isolated.
- Logs and stress tests are streamed via WebSocket.
- Tail logs are streamed from a random loader via SSH.

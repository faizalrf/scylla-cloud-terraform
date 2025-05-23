from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_socketio import SocketIO
from io import StringIO
import subprocess
import os
import threading
from ruamel.yaml import YAML
import json

yaml = YAML()
yaml.preserve_quotes = True  # Preserve quotes in YAML

app = Flask(__name__)
socketio = SocketIO(app)

env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"

running_jobs = {}  # cluster_id: set of running commands

# Load the YAML file (multi-cluster or fallback to single-cluster)
def read_config(file_path='variables.yml'):
    with open(file_path, 'r') as f:
        config = yaml.load(f)
        if "clusters" not in config:
            config = {"clusters": {"c1": config}}  # fallback to single cluster format
        return config

@app.route('/')
def index():
    config = read_config()
    clusters = config.get('clusters', {})
    clusters_info = [
        {
            "cluster_id": cid,
            "cluster_name": cdata.get("cluster_name"),
            "cloud": cdata.get("cloud"),
            "regions": cdata.get("regions"),
        }
        for cid, cdata in clusters.items()
    ]
    return render_template('index.html', clusters_info=clusters_info)

@app.route('/get_config/<cluster_id>')
def get_cluster_config(cluster_id):
    config = read_config()
    clusters = config.get('clusters', {})
    cluster_data = clusters.get(cluster_id)
    if cluster_data:
        stream = StringIO()
        yaml.dump(cluster_data, stream)
        return Response(stream.getvalue(), mimetype='text/plain')
    return jsonify({"error": "Cluster not found"}), 404

@app.route('/update_config/<cluster_id>', methods=['POST'])
def update_config(cluster_id):
    yaml_data = request.data.decode('utf-8')
    new_cluster_data = yaml.load(yaml_data)

    config = read_config()
    clusters = config.get('clusters', {})
    clusters[cluster_id] = new_cluster_data

    # Overwrite the YAML file with updated clusters
    with open('variables.yml', 'w') as f:
        yaml.dump({'clusters': clusters}, f)

    return jsonify({"status": "ok"})

@app.route('/run_script/<script_name>/<cluster_id>')
def run_script(script_name, cluster_id):
    commands = {
        'test': f"./scylla-cloud-operations.sh autotest {cluster_id}",
        'status': f"./scylla-cloud-operations.sh status {cluster_id}",
        'cloudstatus': f"./scylla-cloud-operations.sh cloudstatus {cluster_id}",
        'setup': f"./scylla-cloud-operations.sh setup {cluster_id}",
        'progress': f"./scylla-cloud-operations.sh progress {cluster_id}",
        'initload': f"./scylla-cloud-operations.sh initload {cluster_id}",
        'stresstest': f"./scylla-cloud-operations.sh stresstest {cluster_id}",
        'scaleout': f"./scylla-cloud-operations.sh scaleout {cluster_id}",
        'scaleout2': f"./scylla-cloud-operations.sh scaleout2 {cluster_id}",
        'scalein': f"./scylla-cloud-operations.sh scalein {cluster_id}",
        'scalein2': f"./scylla-cloud-operations.sh scalein2 {cluster_id}",
        'kilload': f"./scylla-cloud-operations.sh kilload {cluster_id}",
        'destroy': f"./scylla-cloud-operations.sh destroy {cluster_id}",
        'tailstress': f"./tail_loader_log.sh {cluster_id}",
        'killtail': f"./kill_tail.sh {cluster_id}",
    }

    command = commands.get(script_name)
    if not command:
        return jsonify({"error": "Invalid script name"}), 400

    running_jobs.setdefault(cluster_id, set()).add(script_name)

    def run_and_emit():
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        for line in iter(process.stdout.readline, b''):
            socketio.emit('log_update', {'data': line.decode().rstrip(), 'cluster_id': cluster_id, 'cmd': script_name})
        process.stdout.close()
        process.wait()
        running_jobs[cluster_id].discard(script_name)
        if not running_jobs[cluster_id]:
            del running_jobs[cluster_id]
        socketio.emit('log_update', {
            'data': f"Command `{script_name}` finished with exit code {process.returncode}",
            'cluster_id': cluster_id,
            'cmd': script_name
        })
    thread = threading.Thread(target=run_and_emit)
    thread.start()

    return jsonify({"status": "started"})

@app.route('/get_monitor_ip/<cluster_id>')
def get_monitor_ip(cluster_id):
    return "0.0.0.0", 204

@app.route('/get_status/<cluster_id>')
def get_status(cluster_id):
    is_running = bool(running_jobs.get(cluster_id))
    return jsonify({"running": is_running})

if __name__ == '__main__':
    app.run(debug=True)
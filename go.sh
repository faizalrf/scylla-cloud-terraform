#!/bin/bash

ENV="./.env"

if [ ! -f "$ENV" ]; then
    echo "'.env' file not found!"
    echo "Please review the env-sample file for instructions"
    echo
    exit 1
fi

source "$ENV"

if [ -z "$TF_VAR_scylla_api_token" ]; then
    echo "The variable TF_VAR_scylla_api_token has an invalid Scylla Cloud token!"
    echo 
    exit 1
else
    echo "Proceed to execute 'terraform' script..."
    echo
    exit 0
fi
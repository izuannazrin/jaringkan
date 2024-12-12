#!/bin/bash

container="$1"

if [[ -z "$container" ]]; then
    containers=( $(docker container ls --format "{{.Names}}" --filter 'name=jk-*' ) )

    if [[ ${#containers[@]} -eq 0 ]]; then
        echo "No running JARINGKAN containers found!"
        exit 1
    elif [[ ${#containers[@]} -gt 1 ]]; then
        echo "Running containers: ${containers[@]}"
        echo "Run $0 <container_name> to log in to a specific container."
        exit 1
    fi

    container="${containers[0]}"
fi

docker exec -it "$container" /usr/libexec/login.sh
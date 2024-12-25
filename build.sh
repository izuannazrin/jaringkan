#!/bin/bash

build_container(){
    docker build -t 'jaringkan-openwrt' container/
}


case "$1" in
    container)
        build_container
        ;;
        
    *)
        cat <<EOF
Usage: $0 <command>

Commands:
    container   Build the container image.
EOF
        ;;
esac
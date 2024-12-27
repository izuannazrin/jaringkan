#!/bin/bash

build_container(){
    docker build -t 'jaringkan-openwrt' container/
}


case "$1" in
    container)
        build_container
        ;;

    support)
        make -C wmediumd/
        make -C mac80211_hwsim_mgmt/
        ;;
        
    *)
        cat <<EOF
Usage: $0 <command>

Commands:
    container   Build the container image.
    support     Build necessary support tools (wmediumd, hwsim_mgmt, etc).
EOF
        ;;
esac
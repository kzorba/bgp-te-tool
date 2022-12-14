#!/bin/bash

SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
cd ${SCRIPTPATH}

export VMXS="vmx1-lab vmx2-lab vmx3-lab"
export SALT_MASTER="kzorba/salt-master:focal-salt_3002-napalm_3.4.1p1"
export SALT_PROXY_MINION="kzorba/salt-proxy-minion:focal-salt_3002-napalm_3.4.1p1"
export GOBGP="kzorba/gobgp"
export EXTERNAL_PEERS="transit1-fr peer1_ix-fr peer2_ix-fr peer3_ix-fr peer4_ix-fr transit2-us peer1_pni-us peer2_pni-us transit3-mf peer1_ix-mf peer2_ix-mf"
export CUSTOMER_PEERS="transit_c1-fr b2b_c1-fr"
export PEERS="${EXTERNAL_PEERS} ${CUSTOMER_PEERS}"

case "$1" in

build)
    echo "==> Building docker images for salt and gobgp"
    echo "*"
    echo "* docker build -t ${SALT_MASTER} -f Dockerfile.salt-master ."
    echo "*"
    docker build -t ${SALT_MASTER} -f Dockerfile.salt-master .
    echo "*"
    echo "* docker build -t ${SALT_PROXY_MINION} -f Dockerfile.salt-proxy-minion ."
    echo "*"
    docker build -t ${SALT_PROXY_MINION} -f Dockerfile.salt-proxy-minion .
    echo "*"
    echo "* docker build -t ${GOBGP} -f Dockerfile.gobgp ."
    echo "*"
    docker build -t ${GOBGP} -f Dockerfile.gobgp .
    echo "==> Done"
;;

start-routers)
    echo "==> Starting routers..."
    echo "==> Check status with $0 router-check"
    docker-compose up -d --remove-orphans vmx1-lab vmx2-lab vmx3-lab
;;

start-salt)
    echo "==> Starting salt master and proxies..."
    docker-compose up -d --remove-orphans salt-master proxy-vmx1-lab proxy-vmx2-lab proxy-vmx3-lab
;;

start-sot)
    echo "==> Starting netbox..."
    cd netbox-docker && docker-compose up -d --remove-orphans
    cd ${SCRIPTPATH}
    echo "==> Starting peering-manager..."
    cd peering-manager-docker && docker-compose up -d --remove-orphans
    cd ${SCRIPTPATH}
;;

start-peers)
    echo "==> Starting BGP peers in topology"
    echo "==> Starting simulated external and customer peers..."
    docker-compose up -d --remove-orphans ${PEERS}
;;

stop-routers)
    echo "==> Stopping routers..."
    docker-compose stop vmx1-lab vmx2-lab vmx3-lab
    docker-compose rm -f vmx1-lab vmx2-lab vmx3-lab
;;

stop-salt)
    echo "==> Stopping salt master and proxies..."
    docker-compose stop salt-master proxy-vmx1-lab proxy-vmx2-lab proxy-vmx3-lab
    docker-compose rm -f salt-master proxy-vmx1-lab proxy-vmx2-lab proxy-vmx3-lab
;;

stop-sot)
    echo "==> Stopping netbox..."
    cd netbox-docker && docker-compose down
    cd ${SCRIPTPATH}
    echo "==> Stopping peering-manager..."
    cd peering-manager-docker && docker-compose down
    cd ${SCRIPTPATH}
;;

stop-peers)
    echo "==> Stopping all peers..."
    docker-compose stop ${PEERS}
    docker-compose rm -f ${PEERS}
;;

stop)
    echo "==> Shutting the lab down..."
    docker-compose down
    $0 stop-sot
    echo "==> Cleaning up local volumes..."
    docker volume prune -f
    echo "==> Done"
;;

status)
    docker ps
    $0 router-check
;;

refresh)
    echo "==> Refreshing docker containers..."
    docker-compose up -d --remove-orphans
    cd netbox-docker && docker-compose up -d --remove-orphans
    cd ${SCRIPTPATH}
    cd peering-manager-docker && docker-compose up -d --remove-orphans
    cd ${SCRIPTPATH}
    echo "==> Done"
;;

load-data)
    FILESDIR="./data"
    TOKEN="0123456789abcdef0123456789abcdef01234567"
    echo "*"
    echo "==> Loading data to netbox"
    echo "*"
    echo
    # RIRs
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8000/api/ipam/rirs/
          --data @${FILESDIR}/netbox-rirs.json | jq '.'"
    eval $cmd
    # Tags
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8000/api/extras/tags/
          --data @${FILESDIR}/netbox-tags.json | jq '.'"
    eval $cmd
    # Aggregates
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8000/api/ipam/aggregates/
          --data @${FILESDIR}/netbox-aggregates.json | jq '.'"
    eval $cmd
    # Prefixes
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8000/api/ipam/prefixes/
          --data @${FILESDIR}/netbox-prefixes.json | jq '.'"
    eval $cmd
    echo
    echo "*"
    echo "==> Loading of data to netbox finished"
    echo "*"
    echo
    echo "*"
    echo "==> Loading data to peering-manager"
    echo "*"
    echo
    # ASNs
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8080/api/peering/autonomous-systems/
          --data @${FILESDIR}/peering-manager-asns.json | jq '.'"
    eval $cmd
    # BGP Groups
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8080/api/peering/bgp-groups/
          --data @${FILESDIR}/peering-manager-bgp-groups.json | jq '.'"
    eval $cmd
    # Internet Exchanges
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8080/api/peering/internet-exchanges/
          --data @${FILESDIR}/peering-manager-internet-exchanges.json | jq '.'"
    eval $cmd
    # Routing policies
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8080/api/peering/routing-policies/
          --data @${FILESDIR}/peering-manager-routing-policies.json | jq '.'"
    eval $cmd
    # Routers
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8080/api/peering/routers/
          --data @${FILESDIR}/peering-manager-routers.json | jq '.'"
    eval $cmd
    # Other - Relationships
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8080/api/bgp/relationships/
          --data @${FILESDIR}/peering-manager-relationships.json | jq '.'"
    eval $cmd
    # Other - Tags
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8080/api/utils/tags/
          --data @${FILESDIR}/peering-manager-tags.json | jq '.'"
    eval $cmd
    # Direct peering sessions
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8080/api/peering/direct-peering-sessions/
          --data @${FILESDIR}/peering-manager-direct-peering-sessions.json | jq '.'"
    eval $cmd
    # IXP connections
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8080/api/net/connections/
          --data @${FILESDIR}/peering-manager-connections.json | jq '.'"
    eval $cmd
    # IXP peering sessions
    cmd="curl -s -X POST -H \"Authorization: Token $TOKEN\" -H \"Content-Type: application/json\"
          http://localhost:8080/api/peering/internet-exchange-peering-sessions/
          --data @${FILESDIR}/peering-manager-ixp-peering-sessions.json | jq '.'"
    eval $cmd
    echo "*"
    echo "==> Loading of data to peering-manager finished"
    echo "*"
    echo
;;

vmx-license-install)
    for r in ${VMXS}
    do
        echo "==> Installing vMX license on $r"
        scp juniper-vmx/license.txt $r:/var/tmp
        ssh $r "request system license add /var/tmp/license.txt"
        ssh $r "show system license"
    done
;;

router-check)
    # Fix private key permissions to access the routers
    chmod 600 ${SCRIPTPATH}/napalm-ssh-keys/lab_id_rsa ${SCRIPTPATH}/napalm-ssh-keys/salty_id_ecdsa
    cd juniper-vmx && ./getpass.sh
    cd ${SCRIPTPATH}
;;

*)
    echo "Usage: $0 command"
    echo
    echo "Available commands:"
    echo "  build: build the Docker images (salt master and proxy minion plus gobgp)"
    echo "  stop: stop the lab using docker-compose and clean up local volumes"
    echo "  status: docker ps plus Juniper routers check"
    echo "  ---"
    echo "  refresh: update all lab containers via docker-compose"
    echo "  vmx-license-install: install a vmx license to the vmx containers"
    echo "  router-check: check proper startup of Juniper routers in the topology"
    echo "  load-data: load data in sources of truth (netbox, peering-manager)"
    echo "  start-routers: start the router containers (Juniper vMX)"
    echo "  start-salt: start salt containers (master and proxies)"
    echo "  start-sot: start the sources of truth (netbox, peering-manager)"
    echo "  start-peers: start the emulated gobgp peers in topology"
    echo "  stop-routers: stop the router containers (Juniper vMX)"
    echo "  stop-salt: stop salt containers (master and proxies)"
    echo "  stop-sot: stop the sources of truth (netbox, peering-manager)"
    echo "  stop-peers: remove all (go)bgp speakers from the topology"
    echo
    exit 1
    ;;

esac

exit 0

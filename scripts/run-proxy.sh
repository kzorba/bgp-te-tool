#!/bin/bash

#
# Salt-Proxy Run Script
#

set -e

# Log Level
PROXY_LOG_LEVEL=${PROXY_LOG_LEVEL:-"debug"}

# Run Salt proxy minion as a Daemon (handled by runit)
/usr/bin/salt-proxy --log-level=$PROXY_LOG_LEVEL --proxyid=$PROXYID

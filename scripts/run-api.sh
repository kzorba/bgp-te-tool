#!/bin/bash

#
# salt-api Run Script
#

set -e

# Log Level
SALT_LOG_LEVEL=${SALT_LOG_LEVEL:-"warning"}

# Run Salt API
/usr/bin/salt-api --log-level=$SALT_LOG_LEVEL

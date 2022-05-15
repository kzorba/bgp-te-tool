#!/bin/bash

#
# Salt-Master Run Script
#

set -e

# Log Level
SALT_LOG_LEVEL=${SALT_LOG_LEVEL:-"warning"}

# Run Salt Master
/usr/bin/salt-master --log-level=$SALT_LOG_LEVEL

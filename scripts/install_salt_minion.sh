#!/bin/bash

# Install salt using bootstrap script
# Download
curl -fsSL https://bootstrap.saltproject.io -o install_salt.sh
curl -fsSL https://bootstrap.saltproject.io/sha256 -o install_salt_sha256

# Verify file integrity
SHA_OF_FILE=$(sha256sum install_salt.sh | cut -d' ' -f1)
SHA_FOR_VALIDATION=$(cat install_salt_sha256)
if [[ "$SHA_OF_FILE" == "$SHA_FOR_VALIDATION" ]]; then
    # After verification, run Linux or macOS / OSX minion install
    echo "Success! Installing..."
    sh install_salt.sh -P -x python3 -X stable 3002
else
    # If hash check fails, don't attempt install
    echo "WARNING: This file is corrupt or has been tampered with."
fi


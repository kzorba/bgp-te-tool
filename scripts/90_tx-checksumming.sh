#!/bin/bash

if [[ ${TX_CHECKSUMMING} == "off" || ${TX_CHECKSUMMING} == "0" ]]
then
   echo "Disabling tx-checksumming offload on eth0"
   /sbin/ethtool -K eth0 tx off
fi
exit 0

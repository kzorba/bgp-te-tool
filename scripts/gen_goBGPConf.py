#!/usr/bin/env python3

"""
A simple script that generates gobgp config for a docker container.
It generates config based on environment variables that are passed to
the container.

"""

__author__ = "Kostas Zorbadelos <kzorba@nixly.net>"
__version__ = "0.1"

import os

if __name__ == "__main__":
    ROUTER_ID = os.getenv('ROUTER_ID', "127.0.0.1")
    LOCAL_AS = os.getenv('LOCAL_AS', 65100)
    PEER_AS = os.getenv('PEER_AS', 65000)
    PEER_IPv4 = os.getenv('PEER_IPv4', "127.0.0.1")
    PEER_IPv6 = os.getenv('PEER_IPv6', "::1")

    gobgp_tmpl = """[global.config]
  as = {0}
  router-id = "{1}"

[[neighbors]]
  [neighbors.config]
    neighbor-address = "{2}"
    peer-as = {3}

[[neighbors]]
  [neighbors.config]
    neighbor-address = "{4}"
    peer-as = {3}
"""
    print(gobgp_tmpl.format(LOCAL_AS, ROUTER_ID, PEER_IPv4, PEER_AS, PEER_IPv6, PEER_AS)) 
    

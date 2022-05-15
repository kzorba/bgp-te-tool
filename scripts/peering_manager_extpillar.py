#!/usr/bin/env python3

"""
Program that fetches BGP peerings from peering-manager django application
[https://github.com/peering-manager/peering-manager].
It works with peering-manager v1.5.2.

It is used to construct the pillar for a proxy minion in Salt.
Each minion corresponds to a router and we pass via the pillar the necessary
information to generate BGP peerings config for the box.

This command is to be run via cmd_json extpillar. Expects

PEERING_MANAGER_API_BASE_URL
PEERING_MANAGER_API_TOKEN

via environment variables to connect to the REST API of peering-manager.
Prints in stdout a json serialized dictionary structure containing the BGP
peering information for a minion.
"""

__author__ = "Kostas Zorbadelos <kzorba@nixly.net>"
__version__ = "1.2"

from os.path import basename
from logging.handlers import SysLogHandler
from ipaddress import IPv4Address, IPv6Address, AddressValueError
import logging
import argparse
import datetime
import sys
import os
import json
import requests
from urllib3.exceptions import InsecureRequestWarning

#----------------- Global settings -------------------
#GLOBALVAR =
#----------------- Global settings -------------------

def isIPv4(a):
    """
    Get a string and check if it is a valid IPv4 address

    Args:
      a (string): a string representing an address

    Returns:
      boolean

    Raises:
      None
    """

    try:
        IPv4Address(a)
        return True
    except AddressValueError:
        return False


def isIPv6(a):
    """
    Get a string and check if it is a valid IPv6 address

    Args:
      a (string): a string representing an address

    Returns:
      boolean

    Raises:
      None
    """

    try:
        IPv6Address(a)
        return True
    except AddressValueError:
        return False


def get_router_info(minion_id, api_base_url, api_token, logger, sslverify=True):
    """
    Gets the router that corresponds to minion_id in peering-manager.

    Location of router is expected either as a tag in the router object in
    peering-manager or in the config_context for the router.
    So, a tag of the form location:XXX means the equipment is in location XXX
    or in case of config_context we expect a key "location" with the proper value
    in JSON.

    Args:
         minion_id (string): the Salt minion_id
         api_base_url (string): the base url of peering-manager django REST API
                                eg: http://peering-manager.infra.msv/api/
         api_token (string): the token used for peering-manager REST API
                             authentication
         logger: a logger object for the program
         sslverify (boolean): whether to check the server cert

    Returns:
         routers (list of dictionaries (records) r):
             r['id'] integer: the id of the router in peering-manager
             r['name'] string: the name of the router
             r['location'] string: the geolocation of the equipment
             r['internet-exchanges'] list of dictionaries (records):
                the internet exchanges the router is attached to

    Return example:
          [
             {'id': 17,
              'name': 'vmx1-lab',
              'location': 'fr',
              'internet-exchanges': [{'id': 12,
                                      'name': 'LAB-IX1',
                                      'ipv4_address': '192.168.100.10',
                                      'ipv6_address': 'fd00:100::10',
                                      'ixp_connection_id': 1}]
             }
          ]

    Raises:
        In case of any errors an empty list is returned and the error is logged

    """

    routers = []
    try:
        headers = {"Authorization": "Token {}".format(api_token),
               "Accept": "application/json"}
        api_routers_url = "{}peering/routers/".format(api_base_url)
        params = {"name": minion_id}
        r = requests.get(api_routers_url, headers=headers, params=params, verify=sslverify)
        logger.debug("Sent request to {0}".format(r.url))
        if (r.status_code != requests.codes.ok):
            r.raise_for_status()
        items = r.json()["results"]
        # the result should be zero or exactly one since we search by router name
        if len(items) > 0:
            item = items[0]
            rec = {}
            rec["id"] = item["id"]
            rec["name"] = item["name"]
            rec["location"] = None
            # first we try to find location in the tags
            tags = item["tags"]
            for t in tags:
                if t["name"].startswith("location:"):
                    rec["location"] = t["name"].split(":")[1]
            # if there is no location in the tags we search in config_context
            if rec["location"] is None:
                if "location" in item["config_context"].keys():
                    rec["location"] = item["config_context"]["location"]
            routers.append(rec)

        # get the IXes the router is attached to via Connections
        api_ix_url = "{}net/connections/".format(api_base_url)
        for rt in routers:
            params = {"router_id": rt["id"]}
            rt["internet-exchanges"] = []
            r = requests.get(api_ix_url, headers=headers, params=params, verify=sslverify)
            logger.debug("Sent request to {0}".format(r.url))
            if (r.status_code != requests.codes.ok):
                r.raise_for_status()
            conns = r.json()["results"]
            for c in conns:
                r_ix = {}
                r_ix["id"] = c["internet_exchange_point"]["id"]
                r_ix["name"] = c["internet_exchange_point"]["slug"].upper()
                r_ix["ipv4_address"] = c["ipv4_address"].split("/")[0]
                r_ix["ipv6_address"] = c["ipv6_address"].split("/")[0]
                r_ix["ixp_connection_id"] = c["id"]
                rt["internet-exchanges"].append(r_ix)

        logger.debug("Routers: {0}".format(routers))
    except:
        logger.exception("get_router_info()")
    return routers


def get_peering_sessions(routers, api_base_url, api_token, logger, sslverify=True):
    """
    Gets the direct and internet exchange sessions for a router.

    routers is a list of dictionaries (records) each representing a
    router. The function returns a dictionary with the representation of
    all direct and internet exchange BGP peerings for the router.
    This will be the data passed via the external pillar to the minion
    via Salt

    Args:
      routers (list of r): list of records (dictionaries) each representing
                           a router, returned by get_router_info()
      api_base_url (string): the base url of peering-manager django REST API
                             eg: http://peering-manager.infra.msv/api/
      api_token (string): the token used for peering-manager REST API
                          authentication
      logger: a logger object for the program
      sslverify (boolean): whether to check the server cert

    Returns:
      peerings (dictionary): a dictionary containing the peerings of the router.
                             It contains the direct peerings plus the peerings
                             via internet exchanges that this
                             router is connected to

    Return examples:
    {'location': 'FR',
     'bgp': {
       'direct-peerings': [
         {
           'group': 'TRANSIT1',
           'peerings': [
             {
               'local_asn': 65000,
               'local_address': '192.168.100.10',
               'neighbor': '192.168.100.110',
               'family': 'inet',
               'peer_asn': 65100,
               'max_prefixes': 750000,
               'description': 'LAB Transit Provider 1 - v4',
               'relationship': 'transit-provider',
               'is_enabled': True,
               'import_policy': 'ACCEPT_ANY',
               'export_policy': 'AS65100_TRANSIT1-FR-V4-OUT',
               'password': None,
               'multihop_ttl': 1
             },
             {
               'local_asn': 65000,
               'local_address': 'fd00:100::10',
               'neighbor': 'fd00:100::110',
               'family': 'inet6',
               'peer_asn': 65100,
               'max_prefixes': 55000,
               'description': 'LAB Transit Provider 1 - v6',
               'relationship': 'transit-provider',
               'is_enabled': True,
               'import_policy': 'ACCEPT_ANY',
               'export_policy': 'AS65100_TRANSIT1-FR-V6-OUT',
               'password': None,
               'multihop_ttl': 1
             }
           ]
         }
       ],
      'internet-exchange-peerings': [
        {
          'group': 'LAB-IX1-PEERS',
          'peerings': [
            {
              'neighbor': '192.168.100.111',
              'local_address': '192.168.100.10',
              'family': 'inet',
              'peer_asn': 65200,
              'max_prefixes': 5000,
              'description': 'LAB Peering partner 1 - v4',
              'relationship': 'ix-peering',
              'is_enabled': True,
              'import_policy': 'ACCEPT_ANY',
              'export_policy': 'AS65200_PEER1_IX-FR-V4-OUT',
              'password': None,
              'multihop_ttl': 1,
              'is_route_server': False
            },
            {
              'neighbor': 'fd00:100::111',
              'local_address': 'fd00:100::10',
              'family': 'inet6',
              'peer_asn': 65200,
              'max_prefixes': 1000,
              'description': 'LAB Peering partner 1 - v6',
              'relationship': 'ix-peering',
              'is_enabled': True,
              'import_policy': 'ACCEPT_ANY',
              'export_policy': 'AS65200_PEER1_IX-FR-V6-OUT',
              'password': None,
              'multihop_ttl': 1,
              'is_route_server': False
            }
          ]
        }
      ]
    }
   }

    Raises:
        None. In case of any errors an empty list is returned and the error
        is logged

    """

    peerings = {}
    headers = {"Authorization": "Token {}".format(api_token),
               "Accept": "application/json"}
    api_direct_peerings_url = "{}peering/direct-peering-sessions/".format(api_base_url)
    api_ix_peerings_url = "{}peering/internet-exchange-peering-sessions/".format(api_base_url)

    for rt in routers:
        peerings["location"] = rt["location"]
        peerings["bgp"] = {}
        peerings["bgp"]["direct-peerings"] = []
        peerings["bgp"]["internet-exchange-peerings"] = []

        # First we get the direct peerings
        logger.debug("Getting direct peering sessions of {}".format(rt["name"]))
        params = {"router_id": rt["id"]}
        r = requests.get(api_direct_peerings_url, headers=headers, params=params, verify=sslverify)
        logger.debug("Sent request to {0}".format(r.url))
        if (r.status_code != requests.codes.ok):
            r.raise_for_status()
        items = r.json()["results"]
        if len(items) > 0:
            logger.debug("Found {} direct peerings for {}".format(len(items), rt["name"]))
            for p in items:
                p_i = {}
                p_i["local_asn"] = p["local_autonomous_system"]["asn"]
                p_i["local_address"] = p["local_ip_address"].split("/")[0]
                p_i["neighbor"] = p["ip_address"].split("/")[0]
                if isIPv4(p_i["neighbor"]):
                    bgp_af = 4
                    p_i["family"] = "inet"
                elif isIPv6(p_i["neighbor"]):
                    bgp_af = 6
                    p_i["family"] = "inet6"
                else:
                    # skip peering with unknown address family
                    next
                p_i["peer_asn"] = p["autonomous_system"]["asn"]
                if (bgp_af == 4):
                    p_i["max_prefixes"] = p["autonomous_system"]["ipv4_max_prefixes"]
                elif (bgp_af == 6):
                    p_i["max_prefixes"] = p["autonomous_system"]["ipv6_max_prefixes"]
                p_i["description"] = "{} - v{}".format(p["autonomous_system"]["name"], bgp_af)
                p_i["relationship"] = p["relationship"]["name"]
                p_i["is_enabled"] = p["enabled"]
                if len(p["import_routing_policies"]) > 0:
                    p_i["import_policy"] = p["import_routing_policies"][0]["slug"].upper()
                else:
                    p_i["import_policy"] = "AS{}-V{}-IN".format(p_i["peer_asn"], bgp_af)
                if len(p["export_routing_policies"]) > 0:
                    p_i["export_policy"] = p["export_routing_policies"][0]["slug"].upper()
                else:
                    p_i["export_policy"] = "AS{}-V{}-OUT".format(p_i["peer_asn"], bgp_af)
                p_i["password"] = p["password"]
                p_i["multihop_ttl"] = p["multihop_ttl"]
                if p["bgp_group"] is not None:
                    bgp_group = p["bgp_group"]["slug"].upper()
                else:
                    bgp_group = "AS{}-GROUP".format(p_i["peer_asn"])
                logger.debug("peering: {} group: {}".format(p_i, bgp_group))
                pos = None
                for i in peerings["bgp"]["direct-peerings"]:
                    if i["group"] == bgp_group:
                        pos = i
                        break
                if pos is not None:
                    pos["peerings"].append(p_i)
                else:
                    peerings["bgp"]["direct-peerings"].append({"group": bgp_group, "peerings": [p_i]})

        # internet exchange peering sessions
        # we get the sessions in the internet exchanges
        # the router is attached to
        logger.debug("Getting internet exchange peering sessions of {}".format(rt["name"]))
        for ix in rt["internet-exchanges"]:
            logger.debug("Internet Exchange: {}".format(ix["name"]))
            params = {"ixp_connection_id": ix["ixp_connection_id"]}
            r = requests.get(api_ix_peerings_url, headers=headers, params=params, verify=sslverify)
            logger.debug("Sent request to {0}".format(r.url))
            if (r.status_code != requests.codes.ok):
                r.raise_for_status()
            items = r.json()["results"]
            if len(items) > 0:
                logger.debug("Found {} IX peerings for {}".format(len(items), rt["name"]))
                bgp_group = "{}-PEERS".format(ix["name"])
                for p in items:
                    p_i = {}
                    #p_i["local_asn"] = p["local_asn"]
                    p_i["neighbor"] = p["ip_address"].split("/")[0]
                    if isIPv4(p_i["neighbor"]):
                        bgp_af = 4
                        p_i["local_address"] = ix["ipv4_address"]
                        p_i["family"] = "inet"
                    elif isIPv6(p_i["neighbor"]):
                        bgp_af = 6
                        p_i["local_address"] = ix["ipv6_address"]
                        p_i["family"] = "inet6"
                    else:
                        # skip peering with unknown address family
                        next
                    p_i["peer_asn"] = p["autonomous_system"]["asn"]
                    if (bgp_af == 4):
                        p_i["max_prefixes"] = p["autonomous_system"]["ipv4_max_prefixes"]
                    elif (bgp_af == 6):
                        p_i["max_prefixes"] = p["autonomous_system"]["ipv6_max_prefixes"]
                    p_i["description"] = "{} - v{}".format(p["autonomous_system"]["name"], bgp_af)
                    p_i["relationship"] = "ix-peering"
                    p_i["is_enabled"] = p["enabled"]
                    if len(p["import_routing_policies"]) > 0:
                        p_i["import_policy"] = p["import_routing_policies"][0]["slug"].upper()
                    else:
                        p_i["import_policy"] = "AS{}_{}-V{}-IN".format(p_i["peer_asn"], ix["name"], bgp_af)
                    if len(p["export_routing_policies"]) > 0:
                        p_i["export_policy"] = p["export_routing_policies"][0]["slug"].upper()
                    else:
                        p_i["export_policy"] = "AS{}_{}-V{}-OUT".format(p_i["peer_asn"], ix["name"], bgp_af)
                    p_i["password"] = p["password"]
                    p_i["multihop_ttl"] = p["multihop_ttl"]
                    p_i["is_route_server"] = p["is_route_server"]
                    logger.debug("IX peering: {} group: {}".format(p_i, bgp_group))
                    pos = None
                    for i in peerings["bgp"]["internet-exchange-peerings"]:
                        if i["group"] == bgp_group:
                            pos = i
                            break
                    if pos is not None:
                        pos["peerings"].append(p_i)
                    else:
                        peerings["bgp"]["internet-exchange-peerings"].append({"group": bgp_group, "peerings": [p_i]})

    logger.debug("peerings: {}".format(peerings))
    return peerings


# Main function
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Get BGP peering data from peering-manager")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s: version {0}".format(__version__))
    parser.add_argument("-c", "--logconsole", help="Provide extra logging to the console of the \
                        program. Syslog facility local1 is used at all times", action="store_true")
    parser.add_argument("-l", "--loglevel", type=str,
                        choices=['debug', 'info', 'warning', 'error'],
                        default='info',
                        help="Set log level. Only log messages with at least \
                        this level of severity")
    parser.add_argument("-s", "--sslnoverify", help="Skip verification of peering-manager server \
                        certificates (eg use of self signed certs)", action="store_true")
    parser.add_argument('minion_id', help='The Salt proxy minion id', type=str)

    args = parser.parse_args()

    # create logger
    logger = logging.getLogger(basename(__file__))
    logger.setLevel(getattr(logging, args.loglevel.upper()))
    # create handler(s). We use syslog and console if requested
    sh = SysLogHandler(facility='local1')
    sh.setLevel(logging.DEBUG)
    syslogformatter = logging.Formatter('%(name)s - %(levelname)s :: %(message)s')
    sh.setFormatter(syslogformatter)
    logger.addHandler(sh)
    if args.logconsole:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        consoleformatter = logging.Formatter('%(asctime)s %(name)s - %(levelname)s :: %(message)s', '%Y-%m-%d %H:%M:%S')
        ch.setFormatter(consoleformatter)
        logger.addHandler(ch)
    sslverify = True
    if args.sslnoverify:
        sslverify = False
    # Suppress only the single warning from urllib3 needed.
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    try:
        extpillar_data = {}
        err_code = 0
        t0 = datetime.datetime.now()
        api_base_url = os.environ.get("PEERING_MANAGER_API_BASE_URL", None)
        if (api_base_url is not None) and (not api_base_url.endswith("/")):
            api_base_url = "{0}/".format(api_base_url)
        api_token = os.environ.get("PEERING_MANAGER_API_TOKEN", None)
        if ((api_base_url is None) or (api_token is None)):
            logger.error("Missing PEERING_MANAGER_API_BASE_URL or PEERING_MANAGER_API_TOKEN variables in environment")
            err_code = 1
        else:
            logger.debug("PEERING_MANAGER_API_BASE_URL: {}".format(api_base_url))
            logger.debug("PEERING_MANAGER_API_TOKEN: {}".format(api_token))
            routers = get_router_info(args.minion_id, api_base_url, api_token, logger, sslverify)
            extpillar_data = get_peering_sessions(routers, api_base_url, api_token, logger, sslverify)
        print(json.dumps(extpillar_data))
        delta_t = datetime.datetime.now() - t0
        logger.info("Execution time: {0}".format(delta_t))
        exit(err_code)
    except SystemExit as e:
        sys.exit(e.code)
    except:
        logger.exception("main()")

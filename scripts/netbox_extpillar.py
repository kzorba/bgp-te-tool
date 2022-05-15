#!/usr/bin/env python3

"""
Program that fetches BGP announcements from netbox django application
[https://github.com/netbox-community/netbox].
It is used to construct the pillar for a proxy minion in Salt.
Each minion corresponds to a router and we pass via the pillar the necessary
information to generate BGP announcements to transits and peers. We search
for prefixes or aggregates in the netbox IPAM that are tagged with a specific
community

This command is to be run via cmd_json extpillar. Expects

NETBOX_API_BASE_URL
NETBOX_API_TOKEN
BGP_ANNOUNCEMENT_COMMUNITY

via environment variables to connect to the REST API of netbox and search for
the relevant bgp announcement community.
Prints in stdout a json serialized dictionary structure containing the BGP
announcements information for a minion.
"""

__author__ = "Kostas Zorbadelos <kzorba@nixly.net>"
__version__ = "1.1"

from os.path import basename
from logging.handlers import SysLogHandler
import logging
import argparse
import datetime
import sys
import os
import json
import requests
import re
from urllib3.exceptions import InsecureRequestWarning

def isBGPcommunity(s):
    """
    Get a string and check if it is a valid BGP community

    Args:
      p (string): a string representing a community

    Returns:
      boolean

    Raises:
      None
    """

    # large communities
    if re.match(r'\d+:\d+:\d+$', s):
        return True
    # regular communities
    elif re.match(r'\d{1,5}:\d{1,5}$', s) or \
         re.match(r'(no-advertise)|(no-export)|(no-export-subconfed)$', s, re.I):
        return True
    # extended communities
    elif re.match(r'(origin)|(target):\d+:\d+$', s) or \
         re.match(r'(origin)|(target):\d+\.\d+\.\d+\.\d+:\d+$', s):
        return True
    return False


def slugify(s, num_chars):
    """
    Get a string and return a "slug" version.

    This is used in netbox django app to produce the url escaped strings
    used in the searches of various objects. These are called "slug" strings
    and are attributes in various netbox objects like tags

    Args:
      s (string): the initial string
      num_chars (int): the number of characters the slug string will be restricted to

    Returns:
      string (the slug version)

    Raises:
      None
    """

    # Remove unneeded chars
    st = re.sub(r'[^\-\.\w\s]', '', s)
    # Trim leading/trailing spaces and dots
    st = re.sub(r'^[\s\.]+|[\s\.]+$', r'', st)
    # Convert spaces and decimals to hyphens
    st = re.sub(r'[\-\.\s]+', r'-', st)
    return (st.lower()[:num_chars])


def get_bgp_announcements(api_base_url, api_token, bgp_announcement_community, logger, sslverify=True):
    """
    Gets the BGP announcement prefixes in NETBOX

    The function returns a dictionary with all the prefixes we want to
    use as BGP announcements to our transits and peers.
    This will be the data passed via the external pillar of salt and
    utilized from the state that creates the configuration for the
    BGP announcements on each AS border router.

    Args:
      api_base_url (string): the base url of netbox django REST API
                             eg: https://netbox.infra.msv/api/
      api_token (string): the token used for netbox REST API
                          authentication
      bgp_announcement_community: the community used for BGP announcements
                                  (eg: 65000:3:1999)
      logger: a logger object for the program
      sslverify (boolean): whether to check the server cert

    Returns:
      announcements (dictionary): a dictionary containing the
                                  the BGP announcement prefixes.
                                  The prefixes should contain various
                                  (large or not) communities
    Return examples:

    Raises:
        None. In case of any errors an empty list is returned and the error
        is logged

    """

    announcements = {}
    announcements["bgp"] = {}
    headers = {"Authorization": "Token {}".format(api_token),
               "Accept": "application/json"}
    api_aggregates_url = "{}ipam/aggregates/".format(api_base_url)
    api_prefixes_url = "{}ipam/prefixes/".format(api_base_url)
    params = {"tag": slugify(bgp_announcement_community, 50)}
    try:
        # First we get any aggregates matching the announcement community
        logger.debug("Getting BGP announcements in netbox aggregates")
        r = requests.get(api_aggregates_url, headers=headers, params=params, verify=sslverify)
        logger.debug("Sent request to {0}".format(r.url))
        if (r.status_code != requests.codes.ok):
            r.raise_for_status()
        items = r.json()["results"]
        if len(items) > 0:
            announcements["bgp"]["announcements"] = []
            logger.debug("Found {} BGP announcements in netbox aggregates".format(len(items)))
            for p in items:
                p_i = {}
                p_i["prefix"] = p["prefix"]
                p_i["address-family"] = p["family"]["label"]
                p_i["route-type"] = "aggregate"
                p_i["next-hop"] = "discard"
                p_i["preference"] = "255"
                p_i["communities"] = []
                for t in p["tags"]:
                    if type(t) is dict:
                        tag = t["name"]
                    else:
                        tag = t
                    if isBGPcommunity(tag):
                        p_i["communities"].append(tag)
                    elif tag.lower().startswith("route-type:"):
                        p_i["route-type"] = tag.lower().split(":")[1]
                    elif tag.lower().startswith("preference:"):
                        p_i["preference"] = tag.lower().split(":")[1]
                    elif tag.lower().startswith("next-hop:"):
                        p_i["next-hop"] = tag.lower().split(":")[1]
                if (p_i["route-type"] == "aggregate"):
                   if (p_i["next-hop"] == "reject"):
                       p_i["next-hop"] = "reject"
                   else:
                       p_i["next-hop"] = "discard"
                announcements["bgp"]["announcements"].append(p_i)
        # Now we get any prefixes matching the announcement community
        logger.debug("Getting BGP announcements in netbox prefixes")
        r = requests.get(api_prefixes_url, headers=headers, params=params, verify=sslverify)
        logger.debug("Sent request to {0}".format(r.url))
        if (r.status_code != requests.codes.ok):
            r.raise_for_status()
        items = r.json()["results"]
        if len(items) > 0:
            if "announcements" not in announcements["bgp"]:
                announcements["bgp"]["announcements"] = []
            logger.debug("Found {} BGP announcements in netbox prefixes".format(len(items)))
            for p in items:
                p_i = {}
                p_i["prefix"] = p["prefix"]
                p_i["address-family"] = p["family"]["label"]
                p_i["route-type"] = "aggregate"
                p_i["next-hop"] = "discard"
                p_i["preference"] = "255"
                p_i["communities"] = []
                for t in p["tags"]:
                    if type(t) is dict:
                        tag = t["name"]
                    else:
                        tag = t
                    if isBGPcommunity(tag):
                        p_i["communities"].append(tag)
                    elif tag.lower().startswith("route-type:"):
                        p_i["route-type"] = tag.lower().split(":")[1]
                    elif tag.lower().startswith("preference:"):
                        p_i["preference"] = tag.lower().split(":")[1]
                    elif tag.lower().startswith("next-hop:"):
                        p_i["next-hop"] = tag.lower().split(":")[1]
                if (p_i["route-type"] == "aggregate"):
                    if (p_i["next-hop"] == "reject"):
                       p_i["next-hop"] = "reject"
                    else:
                       p_i["next-hop"] = "discard"
                announcements["bgp"]["announcements"].append(p_i)
    except:
        logger.exception("get_bgp_announcements()")
    logger.debug("announcements: {}".format(announcements))
    return announcements


# Main function
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Get BGP announcement prefixes from netbox")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s: version {0}".format(__version__))
    parser.add_argument("-c", "--logconsole", help="Provide extra logging to the console of the \
                        program. Syslog facility local1 is used at all times", action="store_true")
    parser.add_argument("-l", "--loglevel", type=str,
                        choices=['debug', 'info', 'warning', 'error'],
                        default='info',
                        help="Set log level. Only log messages with at least \
                        this level of severity")
    parser.add_argument("-s", "--sslnoverify", help="Skip verification of netbox server \
                        certificates (eg use of self signed certs)", action="store_true")

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
        api_base_url = os.environ.get("NETBOX_API_BASE_URL", None)
        if (api_base_url is not None) and (not api_base_url.endswith("/")):
            api_base_url = "{0}/".format(api_base_url)
        api_token = os.environ.get("NETBOX_API_TOKEN", None)
        bgp_announcement_community = os.environ.get("BGP_ANNOUNCEMENT_COMMUNITY", None)
        if ((api_base_url is None) or (api_token is None) or (bgp_announcement_community is None)):
            logger.error("Missing NETBOX_API_BASE_URL or NETBOX_API_TOKEN or BGP_ANNOUNCEMENT_COMMUNITY variables in environment")
            err_code = 1
        else:
            logger.debug("NETBOX_API_BASE_URL: {}".format(api_base_url))
            logger.debug("NETBOX_API_TOKEN: {}".format(api_token))
            logger.debug("BGP_ANNOUNCEMENT_COMMUNITY: {}".format(bgp_announcement_community))
            extpillar_data = get_bgp_announcements(api_base_url, api_token, bgp_announcement_community, logger, sslverify)
        print(json.dumps(extpillar_data))
        delta_t = datetime.datetime.now() - t0
        logger.info("Execution time: {0}".format(delta_t))
        exit(err_code)
    except SystemExit as e:
        sys.exit(e.code)
    except:
        logger.exception("main()")

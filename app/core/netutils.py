import logging
import re
import socket
from subprocess import Popen, PIPE, DEVNULL

import netifaces


logger = logging.getLogger(__name__)


def get_mac_address(host):
    """ Returns MAC address for a hostname. """
    mac_pattern = '(([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})'
    try:
        host = socket.gethostbyname(host)
    except socket.error:
        pass

    with Popen(["arp", "-a", host], stdout=PIPE) as proc:
        for line in proc.stdout:
            line = line.decode("UTF-8")
            if host in line:
                matches = re.findall(mac_pattern, line)
                if matches:
                    return matches[0][0]
        return None


def iter_ipv4_addresses():
    for iface in netifaces.interfaces():
        for ip_obj in netifaces.ifaddresses(iface).get(netifaces.AF_INET, []):
            if "netmask" in ip_obj and "addr" in ip_obj:
                yield ip_obj


def ping_host(host):
    with Popen(["ping", "-c1", "-w2", host], stdout=DEVNULL) as proc:
        proc.wait()
        return proc.returncode == 0

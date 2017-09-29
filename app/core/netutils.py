import logging
import re
import socket
from subprocess import Popen, PIPE


logger = logging.getLogger(__name__)


def get_mac_address(host):
    """ Returns MAC address for a hostname. """
    mac_pattern = '(([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})'
    try:
        host = socket.gethostbyname(host)
    except socket.error:
        pass

    proc = Popen(["arp", "-a", host], stdout=PIPE)
    for line in proc.stdout:
        if host in line:
            matches = re.findall(mac_pattern, line)
            if matches:
                return matches[0][0]
    return None

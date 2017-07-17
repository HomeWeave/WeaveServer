from .main import get_external_ip


EXPORTS = [
    (get_external_ip, "external_ip", "network"),
]

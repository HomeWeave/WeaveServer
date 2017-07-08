import bluetooth

def discover_devices():
    return bluetooth.discover_devices(duration=15, lookup_names=True)



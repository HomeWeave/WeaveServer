def get_required_field(headers, key):
    if key not in headers:
        raise ProtocolError("'{}' is required.".format(key))
    return headers[key]


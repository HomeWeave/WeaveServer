from .static_content_handler import root_handler

controllers = [
    ("/", root_handler),
    #("/api", heartbeat_handler),
]



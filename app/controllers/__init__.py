"""
Exposes all the controller blueprints in a list called controllers. When adding
a new blueprint, add an entry to the controller variable below like:
    controllers = [
        ...,
        (<url_prefix>, blueprint),
    ]
"""
from .static_content_handler import handler as root_handler

controllers = [
    ("/", root_handler),
]



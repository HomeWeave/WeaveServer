from .static_content_handler import root_handler
from .views import view_handler

controllers = [
    ("/", root_handler),
    ("/view", view_handler),
]



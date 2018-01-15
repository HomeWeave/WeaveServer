from app.core.services.api import API, ArgParameter

WEBOS_COMMANDS = [
    API("media_set_mute", "Set mute status.", [
        ArgParameter("mute", "True mutes, False unmutes.", bool)
    ])
]

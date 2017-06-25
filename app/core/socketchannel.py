from flask_socketio import Namespace, emit


class ClientSocket(object):
    def __init__(self):
        pass

    #def send_message(

class NavigationChannel(Namespace):
    def __init__(self, namespace, client):
        self.client = client
        super(Namespace, self).__init__(namespace)

    def on_connect(self):
        pass

    def on_disconnect(self):
        pass

    def on_request_view(self, *args):
        print("Got a request...!!!")
        self.send_view(self.client.view.html())

    def send_view(self, html):
        emit('view', {"html": html})


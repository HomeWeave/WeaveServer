"""
This module implements the basic gevent server that listens to user inputs from
android device.
"""
import logging

import eventlet
from eventlet.queue import LightQueue


logger = logging.getLogger(__name__)



class RemoteControlServer(object):
    def __init__(self, service, host='0.0.0.0', port=15023):
        self.server = eventlet.listen((host, port))
        self.service = service
        self.out_queues = []

    def start(self):
        self.serve_forever()

    def start_sender(self, conn, queue):
        while True:
            item = queue.get()
            conn.write(item)
            conn.flush()

    def serve_forever(self):
        while True:
            try:
                new_sock, _ = self.server.accept()
                logger.info("Client connected.")

                queue = LightQueue()
                self.out_queues.append(queue)

                conn = new_sock.makefile("rw")
                thread = eventlet.spawn_n(self.start_sender, conn, queue)
                eventlet.spawn_n(self.start_receiver, conn, thread, queue)
            except (SystemExit, KeyboardInterrupt):
                break

    def start_receiver(self, conn, thread, out_queue):
        while True:
            line = conn.readline()
            if not line:
                logger.info("RemoteControl client disconnected.")
                break

            res = self.service.process(line)

            if not res:
                continue

            res = res.rstrip() + "\n"
            logger.info("Sending: " + res.strip() + " for " + line)
            out_queue.put(res)
        thread.kill()

    def send_all(self, data):
        for queue in self.out_queues:
            queue.put(data)


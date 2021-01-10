import http.server
import socketserver
import threading


class HTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # print(self.__dict__)
        with HTTPDaemon.lock:
            HTTPDaemon.machines.append(self.client_address)
        http.server.SimpleHTTPRequestHandler.do_GET(self)


class HTTPDaemon:
    lock = threading.Lock()
    machines = []
    barrier = threading.Barrier(2)

    def __init__(self):
        self.httpd = socketserver.ThreadingTCPServer(("", 8000), HTTPRequestHandler)
        self.port = self.httpd.server_address[1]
        self.httpd_thread = threading.Thread(
            target=self.httpd.serve_forever, daemon=True
        )
        # HTTPDaemon.barrier = threading.Barrier(len(machines))

    def start(self):
        self.httpd_thread.start()

    def stop(self):
        self.httpd.shutdown()

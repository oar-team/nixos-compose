import http.server
import sys
import os
import socket
import socketserver
import threading


class HTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HTTPDaemon.directory, **kwargs)

    def log_message(self, format, *args):
        pass

    def log_error(self, format, *args):
        message = "%s - - [%s] %s\n" % (
            self.address_string(),
            self.log_date_time_string(),
            format % args,
        )
        if HTTPDaemon.ctx:
            HTTPDaemon.ctx.elog(message)
        else:
            sys.stderr.write(message)

    def do_GET(self):
        log_message = f"{self.client_address[0]}: HTTP GET {self.path}"
        if HTTPDaemon.ctx:
            HTTPDaemon.ctx.vlog(log_message)
        else:
            print(log_message)
        http.server.SimpleHTTPRequestHandler.do_GET(self)
        with HTTPDaemon.lock:
            HTTPDaemon.machines.append(self.client_address[0])
            # if len(HTTPDaemon.machines) == HTTPDaemon.expected_nb_machines:
            #    HTTPDaemon.get_done_event.set()


class HTTPDaemon:
    lock = threading.Lock()
    machines = []
    expected_nb_machines = 0
    # get_done_event = threading.Event()
    directory = ""
    ctx = None

    def __init__(self, ctx=None, port=0):
        HTTPDaemon.ctx = ctx
        self.httpd = socketserver.ThreadingTCPServer(("", port), HTTPRequestHandler)
        self.port = self.httpd.server_address[1]

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # doesn't have to be reachable
        s.connect(("10.255.255.255", 1))
        self.ip = s.getsockname()[0]

        self.httpd_thread = threading.Thread(
            target=self.httpd.serve_forever, daemon=True
        )

    def start(self, expected_nb_machines=0, directory=os.getcwd()):
        HTTPDaemon.expected_nb_machines = expected_nb_machines
        HTTPDaemon.directory = directory

        self.httpd_thread.start()

        # HTTPDaemon.get_done_event.wait()
        # self.httpd.shutdown()

    def stop(self):
        self.httpd.shutdown()

    # def wait(self, nb_machines):
    #    pass

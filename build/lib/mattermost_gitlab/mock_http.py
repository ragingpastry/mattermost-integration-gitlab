# -*- coding: utf-8 -*-

# Python Future imports
from __future__ import unicode_literals, absolute_import, print_function

# Python System imports
import threading
from six.moves.SimpleHTTPServer import SimpleHTTPRequestHandler
from six.moves.BaseHTTPServer import HTTPServer
from six.moves.http_client import HTTPConnection
import socket

# Django imports
# from django import ...

# Third-party imports

# Smart impulse common modules
# from smartimpulse import ...

# Relative imports

"""
code from http://www.ianlewis.org/en/testing-using-mocked-server

import threading
import mock
import gc

setup:
    def setUp(self):
        self.cond = threading.Condition()
        self.server = mock.http.TestServer(port=9854, self.cond)
        self.cond.acquire()
        self.server.start()

        # Wait until the server is ready
        while not self.server.ready:
            # Collect left over servers so they release their
            # sockets
            import gc
            gc.collect()
            self.cond.wait()

        self.cond.release()

tearDown:
    def tearDown(self):
        self.server.stop_server()
        self.server = None
"""


def get_available_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    __, port = sock.getsockname()
    sock.close()
    return port


class StoppableHttpServer(HTTPServer):
    """http server that reacts to self.stop flag"""

    received_requests = []
    allow_reuse_address = True

    def serve_forever(self, poll_interval=0.5):
        """Handle one request at a time until stopped."""
        self.stop = False
        while not self.stop:
            self.handle_request()


class TestRequestHandler(SimpleHTTPRequestHandler):

    def log_request(self, *args, **kwargs):
        pass

    def do_POST(self):
        """send 200 OK response, with 'OK' as content"""
        # extract any POSTDATA
        self.data = ""
        if "Content-Length" in self.headers:
            self.data = self.rfile.read(int(self.headers["Content-Length"]))

        self.server.received_requests.append({
            'post': self.data,
        })

        self.send_response(200)
        self.end_headers()
        self.wfile.write('OK\n'.encode())

    def do_QUIT(self):
        """send 200 OK response, and set server.stop to True"""
        self.send_response(200)
        self.end_headers()
        self.server.stop = True


class TestServer(threading.Thread):
    """HTTP Server that runs in a thread and handles a predetermined number of requests"""
    TIMEOUT = 10

    def __init__(self, port, cond=None):
        threading.Thread.__init__(self)
        self.port = port
        self.ready = False
        self.cond = cond

    def run(self):
        self.cond.acquire()
        timeout = 0
        self.httpd = None
        while self.httpd is None:
            try:
                self.httpd = StoppableHttpServer(('', self.port), TestRequestHandler)
            except Exception as exc:
                import socket
                import errno
                import time
                if isinstance(exc, socket.error) and errno.errorcode[exc.args[0]] == 'EADDRINUSE' and timeout < self.TIMEOUT:
                    timeout += 1
                    time.sleep(1)
                else:
                    print(exc)
                    self.cond.notifyAll()
                    self.cond.release()
                    self.ready = True
                    raise exc

        self.ready = True
        if self.cond:
            self.cond.notifyAll()
            self.cond.release()
        self.httpd.serve_forever()

    def stop_server(self):
        """send QUIT request to http server running on localhost:<port>"""
        conn = HTTPConnection("127.0.0.1:{}".format(self.port))
        conn.request("QUIT", "/")
        conn.getresponse()


class MockHttpServerMixin(object):

    port = 9854

    def setUp(self):
        super(MockHttpServerMixin, self).setUp()

        try:
            self.server.httpd.received_requests = []
        except AssertionError:
            pass

    @classmethod
    def setUpClass(cls):
        super(MockHttpServerMixin, cls).setUpClass()
        cls.cond = threading.Condition()
        cls.server = TestServer(port=cls.port, cond=cls.cond)
        cls.cond.acquire()
        cls.server.start()

        # Wait until the server is ready
        while not cls.server.ready:
            # Collect left over servers so they release their
            # sockets
            import gc
            gc.collect()
            cls.cond.wait()

        cls.cond.release()

    @classmethod
    def tearDownClass(cls):
        super(MockHttpServerMixin, cls).tearDownClass()
        cls.server.stop_server()
        cls.server.httpd.server_close()
        cls.server = None

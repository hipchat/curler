from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import cgi
import json
import sys
import time


class TestHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        # parse POST data
        env = {'REQUEST_METHOD': 'POST',
               'CONTENT_TYPE': self.headers['Content-Type']}
        form = cgi.FieldStorage(self.rfile, self.headers, environ=env)

        content = 'OK'
        code = 200

        # special behaviors
        if self.path == '/sleep':
            data = json.loads(form['data'].value)
            time.sleep(int(data['secs']))
        elif self.path == '/fail':
            content = 'FAIL'
            code = 500

        self.send_response(code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(content)
        self.wfile.write("\nPOST data: %r" % form['data'].value)
        return


def main():
    try:
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
        server = HTTPServer(('', port), TestHandler)
        print 'Listening on port %d...' % port
        server.serve_forever()
    except KeyboardInterrupt, SystemExit:
        print 'Stopping server.'
        server.socket.close()

if __name__ == '__main__':
    main()

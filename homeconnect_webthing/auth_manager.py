import uuid
import webbrowser
import requests
from threading import Thread
from time import sleep
from string import Template
from http.server import HTTPServer, BaseHTTPRequestHandler
from homeconnect_webthing.auth import Auth
from urllib.parse import urlparse, parse_qs
from typing import List


page_template = Template('''

  <html>
    <head><title>Refresh Token</title></head>
    <body>
       <table>
          <tr>
            <td><b>refresh token</b></td>
            <td>$refresh_token</td>
          </tr>
          <tr>
            <td><b>client secret</b></td>
            <td>$client_secret</td>
          </tr>
        </table>
    </body
  </html>
''')


class RedirectRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self) :
        params = parse_qs(urlparse(self.path).query)
        authorization_code = params['code'][0]
        state = params['state'][0]

        auth: Auth = self.server.handler.token(state, authorization_code)

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        page = page_template.substitute(refresh_token=auth.refresh_token, client_secret=auth.client_secret).encode("UTF-8")
        self.wfile.write(page)
        self.wfile.close()


class RedirectServer(HTTPServer):

    def __init__(self, handler, host: str, port: int):
        self.handler = handler
        HTTPServer.__init__(self, (host, port), RedirectRequestHandler)

    def run(self):
        try:
            self.serve_forever()
        except Exception as e:
            pass

    def start(self):
        Thread(target=self.run, daemon=True).start()

    def stop(self):
        try:
            self.server_close()
        except Exception as e:
            pass


class Authorization:

    URI = "https://api.home-connect.com/security"

    def __init__(self, client_id: str, client_secret:str, scope: str, redirect_host: str = "0.0.0.0", reidrect_port: int = 9855):
        self.state = str(uuid.uuid4())
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.auth = None
        self.redirect_server = RedirectServer(self, redirect_host, reidrect_port)
        self.redirect_server.start()

    def perform(self) -> Auth:
        self.authorize()
        self.wait_until_finished()
        return self.auth

    def authorize(self):
        uri = Auth.URI + "/oauth/authorize?response_type=code&client_id=" + self.client_id + "&scope=" + self.scope + "&state=" + self.state
        webbrowser.open(uri)

    def token(self, state: str, authorization_code: List[str]) -> Auth:
        if self.state == state:
            data = {"client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "authorization_code",
                    "code": authorization_code}
            response = requests.post(Auth.URI + '/oauth/token', data=data)

            data = response.json()
            refresh_token = data['refresh_token']
            access_token = data['access_token']
            self.auth = Auth(refresh_token, self.client_secret)
            self.redirect_server.stop()
            return self.auth
        else:
            return None

    def wait_until_finished(self):
        for i in range(0, 60):
            if self.auth is None:
                sleep(1)

import uuid
import webbrowser
import requests
from threading import Thread
from time import sleep
from string import Template
from http.server import HTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
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



class Session:

    def __init__(self, cookie: SimpleCookie):
        self.cookie = cookie

    @property
    def value(self):
        return self.cookie['SESSION'].value

    @staticmethod
    def create(session : str):
        cookie = SimpleCookie()
        cookie['SESSION'] =  session
        cookie['SESSION']['path'] = '/'
        cookie['SESSION']['max-age'] = str(60*60*24*2)
        cookie['SESSION']['secure'] = True
        return Session(cookie)

    @staticmethod
    def from_headers(headers):
        cookie_header = headers.get('Cookie')
        cookie = SimpleCookie(cookie_header)
        return Session(cookie)


class AuthRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self) :
        path = urlparse(self.path)

        if path.path.startswith("/oauth"):
            if Session.from_headers(self.headers).value == self.server.handler.session:
                params = parse_qs(path.query)
                state = params['state'][0]
                if state == self.server.handler.state:
                    authorization_code = params['code'][0]
                    auth: Auth = self.server.handler.token(authorization_code)
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    page = page_template.substitute(refresh_token=auth.refresh_token, client_secret=auth.client_secret).encode("UTF-8")
                    self.wfile.write(page)
                    self.wfile.close()
                    return
            self.send_response(400)
        else:
            authorize_uri = Auth.URI + "/oauth/authorize?response_type=code&client_id=" + self.server.handler.client_id + "&scope=" + self.server.handler.scope + "&state=" + self.server.handler.state
            self.send_response(302)
            self.send_header('Location', authorize_uri)
            session = Session.create(self.server.handler.session)
            self.send_header("Set-Cookie", session.cookie.output(header='', sep=''))
            self.end_headers()


class AuthServer(HTTPServer):

    def __init__(self, handler, host: str, port: int):
        self.handler = handler
        HTTPServer.__init__(self, (host, port), AuthRequestHandler)

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

    def __init__(self, client_id: str, client_secret:str, scope: str, redirect_host: str = "localhost", redirect_port: int = 9855):
        self.state = str(uuid.uuid4())
        self.session = str(uuid.uuid4())
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.auth = None
        self.start_uri = "http://" + redirect_host + ":" + str(redirect_port)
        self.redirect_server = AuthServer(self, redirect_host, redirect_port)
        self.redirect_server.start()

    @staticmethod
    def perform(client_id: str, client_secret:str, scope: str, redirect_host: str = "localhost", redirect_port: int = 9855) -> Auth:
        authorization = Authorization(client_id, client_secret, scope, redirect_host, redirect_port)
        webbrowser.open(authorization.start_uri)

        for i in range(0, 60):
            if authorization.auth is None:
                sleep(1)
        return authorization.auth

    def token(self, authorization_code: List[str]) -> Auth:
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



# example
# Authorization.perform(client_id='7565664....', client_secret='8C77B22....', scope="IdentifyAppliance%20Dishwasher%20Dryer%20Washer")


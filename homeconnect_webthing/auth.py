import logging
import requests
import webbrowser
from os import path
from datetime import datetime, timedelta
from urllib.parse import urlsplit, parse_qs
from typing import Optional




class FetchAccessToken:

    def __init__(self, token: str = "", issue_time: datetime = datetime.strptime('1970-01-01', '%Y-%m-%d'), expires_in_sec: int = 0):
        self.token = token
        self.issue_time = issue_time
        self.expires_in_sec = expires_in_sec

    @property
    def expiring_date(self) -> datetime:
        return self.issue_time + timedelta(seconds=self.expires_in_sec)

    def is_expired(self):
        return datetime.now() > (self.expiring_date - timedelta(minutes=5))

    def __str__(self):
        return "issued: " + self.issue_time.strftime("%d.%b %H:%M") + ", " + \
               "expires: " + self.expiring_date.strftime("%d.%b %H:%M")


class Auth:

    URI = "https://api.home-connect.com/security"
    DEFAULT_FILENAME = "homeconnect_oauth.txt"

    @staticmethod
    def create(client_id: str, client_secret:str, scope: str = "IdentifyAppliance%20Dishwasher%20Dryer"):
        uri = Auth.URI + "/oauth/authorize?response_type=code&client_id=" + client_id + "&scope=" + scope
        webbrowser.open(uri)

        auth_result = input("Please enter the URL redirected to: ")
        query = urlsplit(auth_result).query
        params = parse_qs(query)
        authorization_code = params['code']

        data = {"client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": authorization_code}
        response = requests.post(Auth.URI + '/oauth/token', data=data)
        data = response.json()
        return Auth(data['refresh_token'], client_secret)

    def __init__(self, refresh_token: str, client_secret: str):
        self.__refresh_token = refresh_token
        self.__client_secret = client_secret
        self.__fetched_access_token = FetchAccessToken()

    @property
    def access_token(self) -> str:
        if self.__fetched_access_token.is_expired():
            logging.info("access token is (almost) expired (" + str(self.__fetched_access_token) + "). Requesting new access token")
            data = {"grant_type": "refresh_token", "refresh_token": self.__refresh_token, "client_secret": self.__client_secret}
            response = requests.post(Auth.URI + '/oauth/token', data=data)
            response.raise_for_status()
            data = response.json()
            self.__fetched_access_token = FetchAccessToken(data['access_token'], datetime.now(), data['expires_in'])
            logging.info("new access token has been created (" + str(self.__fetched_access_token) + ")")
        return self.__fetched_access_token.token

    def store(self, filename : str = DEFAULT_FILENAME):
        logging.info("storing secret file " + path.abspath(filename))
        with open(filename, "w") as file:
            file.write("refresh_token: " + self.__refresh_token + "\n")
            file.write("client_secret: " + self.__client_secret + "\n")

    @staticmethod
    def load(filename : str = DEFAULT_FILENAME) -> Optional:
        if filename is None:
            logging.info("filename is required")
        else:
            if path.isfile(filename):
                logging.info("loading secret file " + path.abspath(filename))
                with open(filename, "r") as file:
                    refresh_line = file.readline()
                    refresh_token = refresh_line[refresh_line.index(":")+1:].strip()
                    client_secret_line = file.readline()
                    client_secret = client_secret_line[client_secret_line.index(":")+1:].strip()
                    return Auth(refresh_token, client_secret)
            else:
                logging.info("secret file " + path.abspath(filename) + " does not exist")
                return None

    def __str__(self):
        return "refresh_token: " + self.__refresh_token + "\n" + "client_secret: " + self.__client_secret

    def __repr__(self):
        return self.__str__()

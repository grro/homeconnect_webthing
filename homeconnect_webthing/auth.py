import logging
import requests
import webbrowser
from os import path
from datetime import datetime, timedelta
from urllib.parse import urlsplit, parse_qs
from typing import Optional, Tuple



class Auth:

    URI = "https://api.home-connect.com/security"
    DEFAULT_FILENAME = "homeconnect_oauth.txt"

    @staticmethod
    def create(client_id: str, client_secret:str, scope: str = "IdentifyAppliance%20Dishwasher"):
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
        self.__access_token, self.__expiring_date = self.__create_access_token()

    @staticmethod
    def __print_valid_to(expiring_date: datetime):
        return "valid until " + str(expiring_date.strftime("%Y-%m-%dT%H:%M:%S"))

    @property
    def access_token(self) -> str:
        if datetime.now() > (self.__expiring_date + timedelta(seconds=60)):
            logging.info("access token expired (" + self.__print_valid_to(self.__expiring_date) + "). Requesting new access token")
            self.__access_token, self.__expiring_date = self.__create_access_token()
        return self.__access_token

    def __create_access_token(self) -> Tuple[str, datetime]:
        data = {"grant_type": "refresh_token",
                "refresh_token": self.__refresh_token,
                "client_secret": self.__client_secret}
        response = requests.post(Auth.URI + '/oauth/token', data=data)
        response.raise_for_status()
        data = response.json()
        expiring_date = datetime.now() + timedelta(seconds=data['expires_in'])
        logging.info("new access token created ("+ self.__print_valid_to(expiring_date) + ")")
        return data['access_token'], expiring_date

    def store(self, filename : str = DEFAULT_FILENAME):
        logging.info("storing secret file " + path.abspath(filename))
        with open(filename, "w") as file:
            file.write("refresh_token: " + self.__refresh_token + "\n")
            file.write("client_secret: " + self.__client_secret + "\n")

    @staticmethod
    def load(filename : str = DEFAULT_FILENAME) -> Optional:
        if filename is not None and path.isfile(filename):
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

import logging
from homeconnect_webthing.app import App, ArgumentSpec
from homeconnect_webthing.auth import Auth
from homeconnect_webthing.homeappliances_webthing import run_server


logging.getLogger('sseclient').setLevel(logging.WARNING)

def main():
    App.run(run_function=lambda args, desc: run_server(description=desc, port=args['port'], refresh_token=args['refresh_token'], client_secret=args['client_secret']),
            packagename="homeconnect_webthing",
            arg_specs=[ArgumentSpec("refresh_token", str, "the oauth2 refresh token", True),
                       ArgumentSpec("client_secret", str, "the oauth2 client_secret", True)])

if __name__ == '__main__':
    main()

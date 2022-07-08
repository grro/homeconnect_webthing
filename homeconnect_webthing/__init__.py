import logging
from homeconnect_webthing.app import App, ArgumentSpec
from homeconnect_webthing.auth import Auth
from homeconnect_webthing.homeappliances_webthing import run_server


logging.getLogger('sseclient').setLevel(logging.WARNING)

def main():
    App.run(run_function=lambda args, desc: run_server(description=desc, port=args['port'], filename=args['authfile']),
            packagename="homeconnect_webthing",
            arg_specs=[ArgumentSpec("authfile", str, "the absolute auth filename such as /root/homeconnect_oauth.txt", True)])


if __name__ == '__main__':
    main()

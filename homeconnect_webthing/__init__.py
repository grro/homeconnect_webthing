from pathlib import Path
from homeconnect_webthing.app import App, ArgumentSpec
from homeconnect_webthing.auth import Auth
from homeconnect_webthing.homeappliances_webthing import run_server


def main():
    App.run(run_function=lambda args, desc: run_server(args['port'], description=desc, filename=args['authfile']),
            packagename="homeconnect_webthing",
            arg_specs=[ArgumentSpec("authfile", str, "the auth file path", True)])


if __name__ == '__main__':
    main()

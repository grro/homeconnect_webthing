from homeconnect_webthing.app import App, ArgumentSpec
from homeconnect_webthing.homeappliances_webthing import run_server


def main():
    App.run(lambda args, desc: run_server(args['port'], description=desc),
            "homeconnect_webthing",
            [ArgumentSpec("period", int, "the period", 56, True)])


if __name__ == '__main__':
    main()

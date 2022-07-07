from homeconnect_webthing.abstract_app import AbstractApp, ArgumentSpec
from homeconnect_webthing.homeappliances_webthing import run_server
from typing import Dict, Any

class MyApp(AbstractApp):

    def do_listen(self, args: Dict[str, Any]) -> bool:
        print('starting webthing server on port ' + str(args['port']))
        run_server(args['port'], description=self.description)
        return True


def main():
    MyApp("homeconnect_webthing", [ArgumentSpec("period", int, "the period", 56, True)]).handle_command()


if __name__ == '__main__':
    main()

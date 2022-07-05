from homeconnect_webthing.abstract_app import AbstractApp
from homeconnect_webthing.homeappliances_webthing import run_server


class MyApp(AbstractApp):

    def do_listen(self, port: int, verbose: bool, args) -> bool:
        return run_server(port, description=self.description)


def main():
    MyApp("homeconnect_webthing", 9080).handle_command()

if __name__ == '__main__':
    main()

from os import system, remove
from os import listdir
from abc import ABC, abstractmethod
import pathlib
import logging
import subprocess
import argparse
from dataclasses import dataclass
from importlib.metadata import metadata, entry_points
from typing import List, Any


@dataclass
class Argument:
    name: str
    dt: type
    description: str
    default_value: Any = None
    required: bool = False

class AbstractApp(ABC):

    def __init__(self, packagename: str, default_port: int = 8644, arguments: List[Argument] = []):
        self.unit = Unit(packagename)
        self.packagename = packagename
        self.default_port = default_port
        self.arguments = arguments
        md = metadata(packagename)
        self.description = md.json.get('description', "")
        for script in entry_points(group='console_scripts'):
            if script.value == packagename + '.__main__:main':
                self.entrypoint = script.name
        print(self.description)

    def print_usage_info(self, port: int) -> bool:
        print("for command options usage")
        print(" sudo " + self.entrypoint + " --help")
        print("example commands")
        print(" sudo " + self.entrypoint + " --command register --port " + str(port) + " " + " ".join(["--" + argument.name + " " + str(argument.default_value) for argument in self.arguments]))
        print(" sudo " + self.entrypoint + " --command listen --port " + str(port) + " " +  " ".join(["--" + argument.name + " " + str(argument.default_value) for argument in self.arguments]))
        if len(self.unit.list_installed()) > 0:
            print("example commands for registered services")
            for service_info in self.unit.list_installed():
                port = service_info[1]
                print(" sudo " + self.entrypoint + " --command deregister --port " + port)
                print(" sudo " + self.entrypoint + " --command log --port " + port)
        return True

    def handle_command(self):
        parser = argparse.ArgumentParser(description=self.description)
        parser.add_argument('--command', metavar='command', required=False, type=str, help='the command. Supported commands are: listen (run the webthing service), register (register and starts the webthing service as a systemd unit, deregister (deregisters the systemd unit), log (prints the log)')
        parser.add_argument('--port', metavar='port', required=False, type=int, help='the port of the webthing serivce')
        parser.add_argument('--verbose', metavar='verbose', required=False, type=bool, default=False, help='activates verbose output')
        for argument in self.arguments:
            parser.add_argument('--' + argument.name, metavar=argument.name, required=argument.required, type=argument.dt, default=argument.default_value, help=argument.description)
        args = parser.parse_args()

        if args.verbose:
            log_level=logging.DEBUG
        else:
            log_level=logging.INFO
        logging.basicConfig(format='%(asctime)s %(name)-20s: %(levelname)-8s %(message)s', level=log_level, datefmt='%Y-%m-%d %H:%M:%S')

        port = self.default_port if args.port is None else args.port
        handled = False
        if args.command is None:
            handled = self.print_usage_info(port)
        elif args.command == 'listen':
            handled = self.do_listen(int(port), args.verbose, args)

    @abstractmethod
    def do_listen(self, port: int, verbose: bool, args) -> bool:
        return False



class Unit:

    def __init__(self, packagename: str):
        self.packagename = packagename


    def __print_status(self, service: str):
        try:
            status = subprocess.check_output("sudo systemctl is-active " + service, shell=True, stderr=subprocess.STDOUT)
            if status.decode('ascii').strip() == 'active':
                print(service + " is running (print log by calling " + "sudo journalctl -n 20 -u " + service + ")")
                return
        except subprocess.CalledProcessError as e:
            pass
        print("Warning: " + service + " is not running")
        system("sudo journalctl -n 20 -u " + service)

    def register(self, port: int, unit: str):
        service = self.servicename(port)
        unit_file_fullname = str(pathlib.Path("/", "etc", "systemd", "system", service))
        with open(unit_file_fullname, "w") as file:
            file.write(unit)
        system("sudo systemctl daemon-reload")
        system("sudo systemctl enable " + service)
        system("sudo systemctl restart " + service)
        self.__print_status(service)

    def deregister(self, port: int):
        service = self.servicename(port)
        unit_file_fullname = str(pathlib.Path("/", "etc", "systemd", "system", service))
        system("sudo systemctl stop " + service)
        system("sudo systemctl disable " + service)
        system("sudo systemctl daemon-reload")
        try:
            remove(unit_file_fullname)
        except Exception as e:
            pass

    def printlog(self, port:int):
        system("sudo journalctl -f -u " + self.servicename(port))

    def servicename(self, port: int):
        return self.packagename + "_" + str(port) + ".service"

    def list_installed(self):
        services = []
        try:
            for file in listdir(pathlib.Path("/", "etc", "systemd", "system")):
                if file.startswith(self.packagename) and file.endswith('.service'):
                    idx = file.rindex('_')
                    port = str(file[idx+1:file.index('.service')])
                    services.append((file, port, self.is_active(file)))
        except Exception as e:
            pass
        return services

    def is_active(self, servicename: str):
        cmd = '/bin/systemctl status %s' % servicename
        proc = subprocess.Popen(cmd, shell=True,stdout=subprocess.PIPE,encoding='utf8')
        stdout_list = proc.communicate()[0].split('\n')
        for line in stdout_list:
            if 'Active:' in line:
                if '(running)' in line:
                    return True
        return False

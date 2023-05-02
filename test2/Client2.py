import asyncio
import logging
import sys
import socket
import json
import http.client
import time
import struct 
import select
SERVER = 'student10.cse.nd.edu'
PORT = '9000'

log = logging.getLogger(__name__)

clients = {}  # task -> (reader, writer)

class Client2:
    heart = "\u2665"
    club = "\u2663"
    diamond = "\u2666"
    spade = "\u2660"
    def __init__(self, game_name):
        self.game_name = game_name
        self.host = SERVER
        self.port = PORT
        self.lastheardfrom = 0
        self.name_retries = 0
        self.server_retries = 0
        self.send_retries = 0
        self.recv_retries = 0
        self.id = -1
        self.grabbing_started = 0
        self.eliminated = 0
        self.init_loop()
        self.mycards = []

        self.connect_to_server()
        while(not self.eliminated):
            self.play_game()

    def init_loop(self):
        log = logging.getLogger("")
        formatter = logging.Formatter("%(asctime)s %(levelname)s " +
                                    "[%(module)s:%(lineno)d] %(message)s")
        # setup console logging
        log.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        log.addHandler(ch)
        log.info("MAIN begin")
        loop = asyncio.get_event_loop()
        #for x in range(200):
        addr = find_name(self.game_name, "AsyncServer")
        make_connection(addr[0], addr[1])
        loop.run_forever()
        log.info("MAIN end")

    def connect_to_server(self):
        # find in name server and connect
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.s.settimeout(30)
        self.find_name(self.game_name, "SpoonsServer")

        self.server_retries = 0
        while(True):
            try:
                res = self.s.connect((self.host, self.port))
                resp = self.recv_resp('')
                self.id = int(resp['id'])
                print('Connected to port: ', self.port)
                print('Welcome! You are player ' + str(self.id) + '!')
                if self.id == 0:
                    print('\nYou are the first player in the circle! You will be picking up from the remaining deck and will begin the flow of cards.')
                break
            except Exception as e:
                print('Connection to server failed. Restarting connection.')
                try:
                    self.s.close()
                except:
                    pass
                self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.s.settimeout(5)
                self.find_name(self.game_name, "SpoonsServer")
                time.sleep(2**self.server_retries)
                self.server_retries+=1

    def make_connection(host, port):

        task = asyncio.Task(handle_client(host, port))

        clients[task] = (self.host, self.port)

        def client_done(task):
            del clients[task]
            log.info("Client Task Finished")
            if len(clients) == 0:
                log.info("clients is empty, stopping loop.")
                loop = asyncio.get_event_loop()
                loop.stop()

        log.info("New Client Task")
        task.add_done_callback(client_done)

    def find_name(game_name, serverName):

            while(True):
                name_server = http.client.HTTPConnection('catalog.cse.nd.edu', '9097')
                name_server.request('GET', '/query.json')
                name_server_entries = json.loads(name_server.getresponse().read().decode())

                for entry in name_server_entries:
                    try:
                        if self.host == None and entry['game_name'] == game_name and entry["serverName"] == serverName: # save the first match
                            self.host = entry['name']
                            self.port = entry['port']
                            self.lastheardfrom = entry['lastheardfrom']

                        elif entry['game_name'] == game_name and entry["serverName"] == serverName:   # if exist more matches --> check lastheardfrom
                            if entry['lastheardfrom'] > lastheardfrom:
                                self.host = entry['name']
                                self.port = entry['port']
                                self.lastheardfrom = entry['lastheardfrom']
                        
                    except KeyError as ke:
                        pass
                if self.host == None:
                    print('Failed to lookup name in catalog. Trying lookup again.')
                    # self.name_retries replaced with x
                    time.sleep(2** self.name_retries)
                    x+=1
                    continue
                else:
                    break


    async def handle_client(host, port):
        log.info("Connecting to %s %d", host, port)
        client_reader, client_writer = await asyncio.open_connection(host,
                                                                        port)
        log.info("Connected to %s %d", host, port)
        try:
            # looking for a hello
            # give client a chance to respond, timeout after 10 seconds
            data = await asyncio.wait_for(client_reader.readline(),
                                            timeout=10.0)

            if data is None:
                log.warning("Expected HELLO, received None")
                return

            sdata = data.decode().rstrip().upper()
            log.info("Received %s", sdata)
            if sdata != "HELLO":
                log.warning("Expected HELLO, received '%s'", sdata)
                return

            # send back a WORLD
            client_writer.write("WORLD\n".encode())

            # wait for a READY
            data = await asyncio.wait_for(client_reader.readline(),
                                            timeout=10.0)

            if data is None:
                log.warning("Expected READY, received None")
                return

            sdata = data.decode().rstrip().upper()
            if sdata != "READY":
                log.warning("Expected READY, received '%s'", sdata)
                return

            echostrings = ['one', 'two', 'three', 'four', 'five', 'six']

            for echostring in echostrings:
                # send each string and get a reply, it should be an echo back
                client_writer.write(("%s\n" % echostring).encode())
                data = await asyncio.wait_for(client_reader.readline(),
                                                timeout=10.0)
                if data is None:
                    log.warning("Echo received None")
                    return

                sdata = data.decode().rstrip()
                log.info(sdata)

            # send BYE to disconnect gracefully
            client_writer.write("BYE\n".encode())

            # receive BYE confirmation
            data = await asyncio.wait_for(client_reader.readline(),
                                            timeout=10.0)

            sdata = data.decode().rstrip().upper()
            log.info("Received '%s'" % sdata)
        finally:
            log.info("Disconnecting from %s %d", host, port)
            client_writer.close()
            log.info("Disconnected from %s %d", host, port)

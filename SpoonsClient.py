import sys
import socket
import json
import http.client

class SpoonsClient:
    def __init__(self, game_name):
        self.game_name = game_name
        self.host = None
        self.port = 0
        self.lastheardfrom = 0

        self.mycards = []
        
        # lookup name and connect to server
        self.connect_to_server()
        #self.play_game()

    def find_name(self):
        self.name_retries = 0
        while(True):
            name_server = http.client.HTTPConnection('catalog.cse.nd.edu', '9097')
            name_server.request('GET', '/query.json')
            name_server_entries = json.loads(name_server.getresponse().read().decode())

            for entry in name_server_entries:
                try:
                    if self.host == None and entry['game_name'] == self.game_name: # save the first match
                        self.host = entry['name']
                        self.port = entry['port']
                        self.lastheardfrom = entry['lastheardfrom']

                    elif entry['game_name'] == self.game_name:   # if exist more matches --> check lastheardfrom
                        if entry['lastheardfrom'] > self.lastheardfrom:
                            self.host = entry['name']
                            self.port = entry['port']
                            self.lastheardfrom = entry['lastheardfrom']
                    
                except KeyError as ke:
                    pass

            if self.host == None:
                print('Failed to lookup name in catalog. Trying lookup again.')
                time.sleep(2**self.name_retries)
                self.name_retries+=1
                continue
            else:
                break

    def connect_to_server(self):
        # find in name server and connect
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.settimeout(5)
        self.find_name()

        self.server_retries = 0
        while(True):
            try:
                res = self.s.connect((self.host, self.port))
                print('Connected')
                break
            except Exception as e:
                print('Connection to server failed. Restarting connection.')
                try:
                    self.s.close()
                except:
                    pass
                self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.s.settimeout(5)
                self.find_name()
                time.sleep(2**self.server_retries)
                self.server_retries+=1

    #def play_game(self):





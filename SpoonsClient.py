import sys
import socket
import json
import http.client
import time

class SpoonsClient:
    def __init__(self, game_name):
        self.game_name = game_name
        self.host = None
        self.port = 0
        self.lastheardfrom = 0
        self.name_retries = 0
        self.server_retries = 0
        self.send_retries = 0
        self.recv_retries = 0

        self.mycards = []
        
        # lookup name and connect to server
        self.connect_to_server()
        self.play_game()

    def find_name(self):
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

    def play_game(self):
        # server will send hand of cards
        self.get_cards()

        while(True):
            print('YOUR HAND:')
            self.display_cards(self.mycards)

            method = input("Enter 'p' to pickup next card\n")
            if method != 'p':
                print('Invalid operation')
                continue

            #new_card = self.pickup()
            #display_cards(new_card)


            # if resp is 'eliminated':
            #   break

    def get_cards(self):
        msg = { 'method': 'get_cards' }
        msg = json.dumps(msg)
        self.send_request(msg)
        resp = self.recv_resp(msg)
        self.mycards = resp['cards']
        ### ??? necessary to return anything here?

    def pickup(self):
        msg = { 'method': 'pickup' }
        msg = json.dumps(msg)
        self.send_request(msg)
        resp = self.recv_resp(msg)
        return resp['card']

    def discard(self, card):
        msg = { 'method': 'discard', 'card': card}
        msg = json.dumps(msg)
        self.send_request(msg)
        resp = self.recv_resp(msg)
        ### ??? necessary to return anything here?
  
    def send_request(self, msg):
        self.send_retries = 0
        bytes_sent = 0

        while(True):
            try:
                bytes_sent = self.s.send(str(len(msg.encode())).encode() + msg.encode())
            except Exception as e:
                print('Connection to server lost. Restarting connection.')
                self.s.close()
                self.connect_to_server()
                continue

            if bytes_sent == 0:
                print('Failed to send request to server. Restarting connection.')
                self.s.close()
                self.connect_to_server()
                time.sleep(2**self.send_retries)
                self.send_retries+=1
            else:
                break

    def recv_resp(self, msg):
        self.recv_retries = 0
        bytes_recv = 0

        while(True):
            try:
                resp = json.loads(self.s.recv(4096).decode())
            except Exception as e:
                print('Connection lost. Restarting connection.')
                self.s.close()
                self.connect_to_server()
                self.send_request(msg)
                continue

            if len(resp) == 0 or resp == -1:
                print('Failed to receive response from server. Restarting connection.')
                self.s.close()
                self.connect_to_server()
                self.send_request(msg)
                time.sleep(2**self.recv_retries)
                self.recv_retries+=1
            else:
                break

        return resp

    def display_cards(self, cards):

        for card in cards:
            if card[1] == 'H':
                suit = "\u2665"
            elif card[1] == 'C':
                suit = "\u2663"
            elif card[1] == 'D':
                suit = "\u2666"
            elif card[1] == 'S':
                suit = "\u2660"

            print(f'+-----+\n|{card[0]}    |\n|{suit}    |\n|     |\n+-----+')

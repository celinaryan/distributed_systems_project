import sys
import socket
import json
import http.client
import time

class SpoonsClient:
    heart = "\u2665"
    club = "\u2663"
    diamond = "\u2666"
    spade = "\u2660"

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
                        print('host:', entry['name'])
                        print('owner:', entry['owner'])
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
        self.s.settimeout(30)
        self.find_name()

        self.server_retries = 0
        while(True):
            try:
                res = self.s.connect((self.host, self.port))
                print('Connected to port: ', self.port)
                break
            except Exception as e:
                print('Connection to server failed. Restarting connection.')
                print("tried port: ", self.port)
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
            print('\nYOUR HAND:')
            self.display_cards(self.mycards, 1)

            method = input("Enter 'p' to pickup next card\n")
            if method != 'p':
                print('Invalid operation')
                continue

            new_card = self.pickup()
            if new_card == None:
                print('No cards in pick up deck yet. Try again.')
                continue
            
            self.mycards.append(new_card)
            print('NEW CARD:')
            self.display_cards([new_card], 1)

            for i, card in enumerate(self.mycards):
                print(str(i) + ': ', end='')
                self.display_cards([card], 0)
            ind = int(input("\tEnter card to discard (0-4): "))

            while ind < 0 or ind > 4:
                print('\tInvalid card selected.')
                ind = int(input("\tEnter card to discard (0-4)"))

            discard_card = self.mycards[ind]
            self.discard(discard_card)
            self.mycards.remove(discard_card)
            
            #if self.four_of_a_kind():
            # instead of checking if four of a kind, have the option to alaways grab spoon, the func will check if four of a kind
            self.grab_spoon()

            # if resp is 'eliminated':
            #   break

    def grab_spoon(self):
        print("Are you ready to grab a spoon?")
        wantSpoon = input("PRESS X TO GRAB SPOON!")
        # user gets correct card line up and grabs spoon
        if wantSpoon == 'X\n':
            if self.four_of_a_kind():
                currTime = time.time_ns()
                # check if im doing the messages right, just doing it based off of the code I saw meghan right
                msg = { 'method': 'grab_spoon', 'time': str(currTime)}
                msg = json.dumps(msg)
                self.send_request(msg)
                resp = self.recv_resp(msg)
                server_ack = json.loads(msg)
                status = server_ack['status']
                if status == 'success':
                    if server_ack['spoons_left'] == 0:
                        print("You got the last spoon. You win!!")
                    else:
                        print("You successfully grabbed a spoon!\nWait for the other players to grab the spoons for the next round.")
                 ## print whether eliminated or moving on
                 ##return resp
            else:
                print("Invalid cards to grab spoon. Keep playing!")
       
       


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
        if resp['result'] == 'success':
            return resp['card']
        else:
            return None

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

    def four_of_a_kind(self):
        if self.mycards[0][:-1] == self.mycards[1][:-1] == self.mycards[2][:-1] == self.mycards[3][:-1]:
            return 1


    def display_cards(self, cards, graphics):
        suits = [0,0,0,0]
        tens = [0,0,0,0] # array of booleans saying if its a ten or not

        for index, card in enumerate(cards):
            if card[-1:] == 'H':
                suits[index] = self.heart
            elif card[-1:] == 'C':
                suits[index] = self.club
            elif card[-1:] == 'D':
                suits[index] = self.diamond
            elif card[-1:] == 'S':
                suits[index] = self.spade
            if card[:-1] == 10:
                tens[index]=1
            else:
                tens[index]=0

        if graphics:
            # check that tens works
            # adjust for different spacing with 10 (two digit number)
            print(f'\t+-----+\t\t+-----+\t\t+-----+\t\t+-----+\t\t')
            if tens[0]==1:
                print(f'\t|{cards[0][:-1]}   |\t', end='')
            else:
                print(f'\t|{cards[0][:-1]}    |\t', end='')
            if tens[1]==1:
                print(f'\t|{cards[1][:-1]}   |\t', end='')
            else:
                print(f'\t|{cards[1][:-1]}    |\t', end='')
            if tens[2]==1:
                print(f'\t|{cards[2][:-1]}   |\t', end='')
            else:
                print(f'\t|{cards[2][:-1]}    |\t', end='')
            if tens[3]==1:
                print(f'\t|{cards[3][:-1]}   |\t\t')
            else:
                print(f'\t|{cards[3][:-1]}    |\t\t')
            print(f'\t|{suits[0]}    |\t\t|{suits[1]}    |\t\t|{suits[2]}    |\t\t|{suits[3]}    |\t\t')
            print(f'\t|     |\t\t|     |\t\t|     |\t\t|     |\t\t')
            print(f'\t+-----+\t\t+-----+\t\t+-----+\t\t+-----+\t\t')
        else:
            print(f'{card[:-1]}{suit}')




        # for card in cards:
        #     if card[-1:] == 'H':
        #         suit = self.heart
        #     elif card[-1:] == 'C':
        #         suit = self.club
        #     elif card[-1:] == 'D':
        #         suit = self.diamond
        #     elif card[-1:] == 'S':
        #         suit = self.spade

        #     if graphics:
        #         # adjust for different spacing with 10 (two digit number)
        #         if card[:-1] == '10':
        #             print(f'\t+-----+\n\t|{card[:-1]}   |\n\t|{suit}    |\n\t|     |\n\t+-----+')
        #         else:
        #             print(f'\t+-----+\n\t|{card[:-1]}    |\n\t|{suit}    |\n\t|     |\n\t+-----+')
        #     else:
        #         print(f'{card[:-1]}{suit}')

import sys
import socket
import json
import http.client
import time
import struct 
import select
from ClientAsync import *
import asyncio

class SpoonsClient:
    heart = "\u2665"
    club = "\u2663"
    diamond = "\u2666"
    spade = "\u2660"

    def __init__(self, game_name):
        self.game_name = game_name
        #self.player_name = player_name
        self.host = None
        self.port = 0
        self.lastheardfrom = 0
        self.name_retries = 0
        self.server_retries = 0
        self.send_retries = 0
        self.recv_retries = 0
        self.id = -1
        self.grabbing_started = 0
        self.eliminated = 0
        # self.multicast_group = '224.3.29.71'
        # self.spoon_server_address = ('', 10000)
        # self.spoon_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.mycards = []
        
        # lookup name and connect to server
        self.connect_to_server()
        while(not self.eliminated):
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

        self.s.settimeout(30)
        self.find_name()

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
                self.find_name()
                time.sleep(2**self.server_retries)
                self.server_retries+=1

    def play_game(self):
        # connect to async future loop
        # check that self (first param) works/ is right, 
        clientAsyncLoop  = ClientAsync(self, self.host, self.port)
        self.grabbing_started = clientAsyncLoop
        # server will send hand of cards
        self.get_cards()

        # join UDP multicast group for spoon grab messages
        # self.spoon_sock.bind(self.spoon_server_address)
        # group = socket.inet_aton(self.multicast_group)
        # mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        # self.spoon_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # want to do while ClientAsyncLoop?
        # await loop.clientAsyncLoop
        while(self.grabbing_started == 0):
            print('\nYOUR HAND:')
            self.display_cards(self.mycards, 1)

            method = input("Enter 'p' to pickup next card\nEnter 'x' to try to grab a spoon\n")

            if method != 'p' and method != 'x':
                print('Invalid operation')
                continue

            if method == 'x':
                print('GRABBING SPOON')
                self.grab_spoon()

            if method == 'p':
                new_card = self.pickup()
                if new_card == 'next_round':
                    return
                elif new_card == 'eliminated':
                    return

                elif new_card == None:
                    print('No cards in pick up deck yet. Try again.')
                    continue
                
                self.mycards.append(new_card)
                print('NEW CARD:')
                self.display_cards([new_card], 1)

                for i, card in enumerate(self.mycards):
                    print(str(i) + ': ', end='')
                    self.display_cards([card], 0)

                ind = input("\tEnter card to discard (0-4): ")

                while ind not in ['0', '1', '2', '3', '4']:
                    print('\tInvalid card selected.')
                    ind = input("\tEnter card to discard (0-4)")

                ind = int(ind)

                discard_card = self.mycards[ind]
                resp = self.discard(discard_card)
                if resp == 'next_round' or resp == 'eliminated':
                    return

                self.mycards.remove(discard_card)
            self.grabbing_started = clientAsyncLoop
        else:
            self.grab_spoon()
    # def check_spoon_grab(self):
    #     #while 1:
    #     print('checking spoons')
    #     ready, _, _ = select.select([self.spoon_sock], [], [], 0)
    #     for s in ready:
    #         print('got in here')
    #         data, addr = self.spoon_sock.recvfrom(1024)
    #         data = json.loads(data.decode())
    #         if data['msg'] == 'SPOON GRABBED! YOU HAVE 10 SECONDS TO TRY AND GRAB A SPOON!':
                
    #             print(data['msg'], flush=True)
    #             method = input('ENTER x TO TRY TO GRAB A SPOON!\n')
    #             self.spoon_sock.sendto('ack', addr)

    def grab_spoon(self):
        print("Are you ready to grab a spoon?")
        wantSpoon = input("PRESS x TO GRAB SPOON!")
        # user gets correct card line up and grabs spoon
        if wantSpoon == 'x\n':
            # first person to grab spoon
            if self.four_of_a_kind() and self.grabbing_started == 0:
                time = curr_time.time_ns()
                msg = { 'method': 'grab_spoon','time': str(time)}
                msg = json.dumps(msg)
                self.send_request(msg)
                server_ack = json.loads(msg)
                status = server_ack['status']
                if status == 'success':
                    if server_ack['spoons_left'] == 0:
                        print("You got the last spoon. You win!!")
                    else:
                        print("You successfully grabbed a spoon!\nWait for the other players to grab the spoons for the next round.")
            elif not self.four_of_a_kind and self.grabbing_started == 0:
                print("\nInvalid cards to grab spoon. Keep playing!")
                return
            elif self.grabbing_started == 1:
                msg = { 'method': 'grab_spoon','time': str(time)}
                msg = json.dumps(msg)
                self.send_request(msg)
                resp = self.recv_resp(msg)
                resp = json.dumps(resp)
                server_ack = json.loads(resp)
                if server_ack['result'] == 'next_round':
                    print('SUCCESS!')
                    print('\tYou successfully grabbed a spoon. Moving on to the next round.')
                    return 'next_round'
                elif server_ack['result'] == 'eliminated':
                    print('TOO SLOW')
                    print('\tYou were last to grab a spoon. You have been ELIMINATED.')
                    self.eliminated = 1
                    return 'eliminated'
        else:
            # in case user doesnt press x but grabbing has begun
            if(grabbing_started==1)
                print("Are you sure you don't want to grab a spoon?\n")
                self.grab_spoon()
            else: # keep playing
                return
            # print('before')
            # data, addr = self.spoon_sock.recvfrom(1024)
            # print('after')

            # server_ack = json.loads(msg)
            # status = server_ack['status']
            # if status == 'success':
            #     if server_ack['spoons_left'] == 0:
            #         print("You got the last spoon. You win!!")
            #     else:
            #         print("You successfully grabbed a spoon!\nWait for the other players to grab the spoons for the next round.")
                ## print whether eliminated or moving on
                ##return resp
        
       

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
        #if resp['method'] == 'GRAB':
            # self.grabbing_started = 1
            # x = input('GRABBING STARTED!\n\tENTER x TO GRAB! : ')
            # return self.grab_spoon()

        if resp['result'] == 'success':
            return resp['card']
        else:
            return None

    def discard(self, card):
        msg = { 'method': 'discard', 'card': card}
        msg = json.dumps(msg)
        self.send_request(msg)
        resp = self.recv_resp(msg)
        #if resp['method'] == 'GRAB':
        #    self.grabbing_started = 1
        #    x = input('GRABBING STARTED!\n\tENTER x TO GRAB!')
        #    return self.grab_spoon()
        return None
  
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

        if(len(cards) == 4):

            for index, card in enumerate(cards):
                if card[-1:] == 'H':
                    suits[index] = self.heart
                elif card[-1:] == 'C':
                    suits[index] = self.club
                elif card[-1:] == 'D':
                    suits[index] = self.diamond
                elif card[-1:] == 'S':
                    suits[index] = self.spade
                if card[:-1] == '10':
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


        else:

            for card in cards:
                if card[-1:] == 'H':
                    suit = self.heart
                elif card[-1:] == 'C':
                    suit = self.club
                elif card[-1:] == 'D':
                    suit = self.diamond
                elif card[-1:] == 'S':
                    suit = self.spade

                if graphics:
                    # adjust for different spacing with 10 (two digit number)
                    if card[:-1] == '10':
                        print(f'\t+-----+\n\t|{card[:-1]}   |\n\t|{suit}    |\n\t|     |\n\t+-----+')
                    else:
                        print(f'\t+-----+\n\t|{card[:-1]}    |\n\t|{suit}    |\n\t|     |\n\t+-----+')
                else:
                    print(f'{card[:-1]}{suit}')

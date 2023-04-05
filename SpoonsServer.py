import sys
import socket
import json
import os
import select
from CardDeck import *
import time

class SpoonsServer:
    def __init__(self, name):
        self.master = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.name_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.port = 0
        self.name = name
        self.last_sent = 0

        self.players = []
        self.players_info = {}
        self.num_players = 0
        self.num_spoons = 0
        self.deck = CardDeck()
        # ??? self.spoon_port = 

        self.master.bind((socket.gethostname(), self.port))
        if(self.master.listen(5) == -1):
            print('Failed to listen on port ' + str(self.master.getsockname()[1]))

        print('Listening on port ' + str(self.master.getsockname()[1]))
        self.port = self.master.getsockname()[1]
        self.game_init_time = time.time_ns()
        self.game_over = 0

        # will continue playing games until server is killed
        while True:
            if self.last_sent == 0 or time.time_ns() - self.last_sent > 6e+10:
                self.send_udp()
                self.last_sent = time.time_ns()

            # accept connections to join while under max number of players, or wait 10 sec and continue with current number
            ### ??? possibly replace 13  below in loop with number of expected players that would be passed into the server somehow?
            while self.num_players < 13 or time.time_ns() - self.game_init_time > 1e+10:
                (new_player, addr) = self.master.accept()
                self.players.append(new_player)
                self.num_players += 1

            # if no players joined in the 10 seconds, wait again
            if self.num_players == 0:
                continue

            self.play_game()

        
    def play_game(self):
        self.deal_cards()

        # TODO: set pickup pile of player #0 to be remaining_cards in deck object
    
        while game_over == 0:
            if self.last_sent == 0 or time.time_ns() - self.last_sent > 6e+10:
                self.send_udp()
                self.last_sent = time.time_ns()

            ready, _, _ = select.select(self.players, [], [])
            random.shuffle(ready)   ### ??? make service more fair? is there a way to order them in the order the messages were recv'ed?

            for player in ready:
                # player socket closed
                if player.fileno() == -1:
                    self.players.remove(player)
                    del self.players_info[player]
                    self.players -= 1
                    self.spoons -= 1
                    continue  # continue to next round


            #### ??? right now i have this using chunking like if client sends length of msg, not sure if we wanted this so we can def take out
            try: 
                    bytes_to_read = client.recv(2).decode()
                except ConnectionResetError as cre:
                    break

                if bytes_to_read == '':
                    self.clients.remove(client)
                    client.close()
                    continue

                msg = client.recv(int(bytes_to_read)).decode()
                bytes_read = len(msg)

                if bytes_read == 0:
                    self.clients.remove(client)
                    client.close()
                    continue

                if(msg == -1):
                    print('Failed to recieve message. Please try again.')
                    continue

                while int(bytes_read) < int(bytes_to_read):
                    msg += client.recv(int(bytes_to_read) - bytes_read).decode()

                response = self.execute_msg(msg)
                response = json.dumps(response)
                client.send(response.encode())
                
        return


    def execute_msg(self, msg):
        msg = json.loads(msg)

        method = msg['method']
        # TODO: handle pickup, putdown, and spoon requests from clients
        # if method == 'pick_up':


    def deal_cards(self):
        hands = self.deck.deal_cards(self.num_players)

        for i, player in enumerate(self.players_info.values()):
            player['cards'] = hands[i]


    def send_udp(self):
        name_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        msg = { "type" : "hashtable", "owner" : "mnovak5", "port" : self.port, "name" : self.name }
        result = name_server.sendto(json.dumps(msg).encode(), (socket.gethostbyname('catalog.cse.nd.edu'), 9097))

        while(result == -1):
            self.last_sent = time.time_ns()
            msg = { "type" : "hashtable", "owner" : "mnovak5", "port" : self.port, "name" : self.name }
            result = name_server.sendto(json.dumps(msg).encode(), (socket.gethostbyname('catalog.cse.nd.edu'), 9097))

        name_server.close()
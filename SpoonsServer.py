import sys
import socket
import json
import os
import select
from CardDeck import *
import time
import asyncio

class SpoonsServer:
    def __init__(self, game_name, expected_players):
        self.master = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.name_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.port = 9000
        self.game_name = game_name
        self.last_sent = 0
        self.BroadCastQueue = []
        self.multicast_group = ('224.3.29.71', 10000)
        self.multicast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.multicast_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, (b'1'))

        
        self.players = []
        self.players_info = {}
        self.expected_players = expected_players
        self.num_players = 0
        self.num_spoons = 0
        self.deck = CardDeck()
        self.discard_pile = []
        self.timeSpoonGrabbed = -1
        self.first_spoon_grabbed = 0
        self.moving_forward = []

        # for port already used error
        for i in range(1,15):
            try:
                self.master.bind((socket.gethostname(), self.port))
                break
            except:
                self.port += 1
        
        if(self.master.listen(5) == -1):
            print('Failed to listen on port ' + str(self.master.getsockname()[1]))

        print('Listening on port ' + str(self.master.getsockname()[1]))
        self.port = self.master.getsockname()[1]
        self.game_init_time = time.time_ns()
        self.round_over = 0

        # will continue playing games until server is killed
        while True:
            if self.last_sent == 0 or time.time_ns() - self.last_sent > 6e+10:
                self.send_udp()
                self.last_sent = time.time_ns()

            print('Game loading...')

            while self.num_players < self.expected_players:

                ### this wasn't working rn but could add something that conintues with however many players you have rn it you go over a time limit
                # if time.time_ns() - self.game_init_time > 1e+10:
                #     self.game_init_time = time.time_ns()
                #     break

                (new_player, addr) = self.master.accept()
                self.players.append(new_player)
                self.init_player_info(new_player, self.num_players)
                print('\tPlayer', self.num_players, 'joined!')
                msg = { 'method': 'join_game', 'status': 'success', 'id': self.num_players }
                resp = json.dumps(msg).encode()
                new_player.send(resp)
                self.num_players += 1
                self.game_init_time = time.time_ns()

            ### then if no players joined in the time limit, could wait again or quit
            # if self.num_players == 0:
            #     continue

            while self.num_players > 1:
                print('Starting game!')
                self.play_game() 

            #### send winner message to the winning player 

    def play_game(self):
        self.deal_cards()

        ### TAKE OUT AFTER DEBUGGING ###
        self.players_info[self.players[0]]['cards'] = ['4H', '4D', '4S', '4C']
        ################################

        self.first_spoon_grabbed = 0
        self.num_spoons = self.num_players - 1
        # Set pickup pile of player #0 to be remaining_cards in deck object
        self.players_info[self.players[0]]['pickup_deck'] = self.deck.remaining_cards
    
        while self.round_over == 0:
            if self.last_sent == 0 or time.time_ns() - self.last_sent > 6e+10:
                self.send_udp()
                self.last_sent = time.time_ns()

            ready, _, _ = select.select(self.players, [], [])
            random.shuffle(ready)

            for player in ready:
                # player socket closed
                if player.fileno() == -1:
                    self.players.remove(player)
                    del self.players_info[player]
                    self.players -= 1
                    self.spoons -= 1
                    continue  # continue to next round

            try: 
                bytes_to_read = player.recv(2).decode()
            except ConnectionResetError as cre:
                break

            if bytes_to_read == '':
                self.players.remove(player)
                del self.players_info[player]
                player.close()
                continue

            msg = player.recv(int(bytes_to_read)).decode()
            bytes_read = len(msg)

            if bytes_read == 0:
                self.players.remove(player)
                del self.players_info[player]
                player.close()
                continue

            if(msg == -1):
                print('Failed to recieve message. Please try again.')
                continue

            while int(bytes_read) < int(bytes_to_read):
                msg += player.recv(int(bytes_to_read) - bytes_read).decode()

            response = self.execute_msg(player, msg)

            # eliminate player
            if response['result'] == 'eliminated':
                response = json.dumps(response)
                player.send(response.encode())
                self.players_info.pop(player)
                self.players.remove(player)
                return

            response = json.dumps(response)
            player.send(response.encode())
            
        return

    # adds a player to player_info and intiializes it's values
    def init_player_info(self, player, num):
        self.players_info[player] = {
                                        'id': num,
                                        'cards': [],
                                        'pickup_deck': [],
                                        'player_num': self.num_players,
                                        'spoon_grabbed': 0
                                    }

    def execute_msg(self, player, msg):
        grab_msg = { 'method': 'GRAB', 'result': '' }
        msg = json.loads(msg)
        method = msg['method']

        # TODO: handle get_cards, pickup, putdown, and spoon requests from clients
        if method == 'get_cards':
            resp = { 'method': 'get_cards', 'result': 'success', 'cards': self.players_info[player]['cards'] }
            return resp

        elif method == 'pickup':
            if self.first_spoon_grabbed:
                return grab_msg

            if len(self.players_info[player]['pickup_deck']) == 0:

                if player == self.players[0]:
                    if self.discard_pile == []:
                        resp = { 'method': 'pickup', 'result': 'failure', 'message': 'No cards in pickup deck. Try again.' }
                        return resp
                    else:
                        self.players_info[player]['pickup_deck'] = self.discard_pile
                        self.discard_pile = []

                else:
                    resp = { 'method': 'pickup', 'result': 'failure', 'message': 'No cards in pickup deck. Try again.' }
                    return resp

            new_card = self.players_info[player]['pickup_deck'].pop()
            self.players_info[player]['cards'].append(new_card)
            resp = { 'method': 'pickup', 'result': 'success', 'card': new_card }
            return resp

        elif method == 'discard':
            if self.first_spoon_grabbed:
                return grab_msg

            self.players_info[player]['cards'].remove(msg['card'])
            next_ind = self.players_info[player]['player_num'] + 1

            # if last player, go to discard pile
            if next_ind == self.num_players:
                self.discard_pile.append(msg['card'])
            # else into next player's pickup deck
            else:
                self.players_info[self.players[next_ind]]['pickup_deck'].append(msg['card'])

            resp = { 'method': 'discard', 'result': 'success' }
            return resp

        elif method == 'grab_spoon': 
            self.spoon_multicast() 

            for p in self.players:
                if self.players_info[p]['player_num'] in self.moving_forward:
                    resp = {'result': 'next_round'}
                    self.num_spoons -= 1
                else:
                    resp = { 'result': 'eliminated' }
                    self.num_players -= 1

            self.round_over = 1
            #self.reset()
            return resp


    def spoon_multicast(self):
        self.multicast_sock.settimeout(10)

        try:
            # send msg to the multicast group
            msg = json.dumps({ 'msg': 'SPOON_GRABBED! YOU HAVE 10 SECONDS TO TRY AND GRAB A SPOON!' }).encode()
            
            print('sending', msg)

            result = self.multicast_sock.sendto(msg, self.multicast_group)

            while True:
                try:
                    # data will be player_num
                    print(self.multicast_sock)
                    data, addr = self.multicast_sock.recvfrom(1024)
                except socket.timeout:
                    print('timed out no more responses')
                    break
                else:
                    print('received', data.decode(), 'from', addr)
                    self.moving_forward.append(data)
        finally:
            print('done multicasting')
            

    def deal_cards(self):
        hands = self.deck.deal_cards(self.num_players)

        for i, player in enumerate(self.players_info.values()):
            player['cards'] = hands[i]


    def send_udp(self):
        name_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        msg = { "type" : "hashtable", "owner" : "mnovak5", "port" : self.port, "game_name" : self.game_name }
        result = name_server.sendto(json.dumps(msg).encode(), (socket.gethostbyname('catalog.cse.nd.edu'), 9097))

        while(result == -1):
            self.last_sent = time.time_ns()
            msg = { "type" : "hashtable", "owner" : "mnovak5", "port" : self.port, "game_name" : self.game_name }
            result = name_server.sendto(json.dumps(msg).encode(), (socket.gethostbyname('catalog.cse.nd.edu'), 9097))

        name_server.close()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Invalid number of arguments')
        print('Usage: python3 SpoonsServer.py <GAME_NAME> <NUM_PLAYERS>')
        exit(1)
    else:
        game_name = sys.argv[1]
        num_players = int(sys.argv[2])

    if num_players < 2:
        print('Need at least 2 players')
        exit(1)

    ss = SpoonsServer(game_name, num_players)
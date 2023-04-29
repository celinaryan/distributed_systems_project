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
        # self.multicast_group = ('224.3.29.71', 10000)
        # self.multicast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self.multicast_sock.settimeout(0.2)
        # self.multicast_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, (b'1'))

        
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
        self.game_over = 0

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

                # i want to see if i can get this to work
                # instead of saying player 0 joined, want to see the name of person joined
                #print('\tPlayer: ', self.num_players, '\nWith name: ',str(new_player.player_name), 'joined!\n')
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

        self.first_spoon_grabbed = 0
        self.num_spoons = self.num_players - 1
        # Set pickup pile of player #0 to be remaining_cards in deck object
        self.players_info[self.players[0]]['pickup_deck'] = self.deck.remaining_cards
    
        while self.game_over == 0:
            if self.last_sent == 0 or time.time_ns() - self.last_sent > 6e+10:
                self.send_udp()
                self.last_sent = time.time_ns()

            ready, _, _ = select.select(self.players, [], [])
            random.shuffle(ready)   ### ??? make service more fair? is there a way to order them in the order the messages were recv'ed?
                                    # yes I think that's good

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
                                        'spoon_grabbed': 0,
                                        'player_name': ''
                                    }

    def execute_msg(self, player, msg):
        grab_msg = { 'method': 'GRAB', 'result': '' }
        msg = json.loads(msg)
        method = msg['method']

        # TODO: handle get_cards, pickup, putdown, and spoon requests from clients
        if method == 'get_cards':
            resp = { 'method': 'get_cards', 'result': 'success', 'cards': self.players_info[player]['cards'] }

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

        elif method == 'grab_spoon':  

            # first spoon to be grabbed
            if self.first_spoon_grabbed == 0:
                self.first_spoon_grabbed = 1
                self.num_spoons -= 1
                resp = {'result': 'next_round'}

            elif self.num_spoons > 0:
                self.num_spoons -= 1
                resp = {'result': 'next_round'}

            # remove last to grab
            elif self.num_spoons == 0:
                self.num_players -= 1
                resp = { 'result': 'eliminated' }

        return resp


    # def spoon_multicast(self):
    #     self.multicast_sock.settimeout(5)

    #     # send msg to the multicast group
    #     print('1 here')
    #     msg = json.dumps({ 'msg': 'SPOON_GRABBED! YOU HAVE 10 SECONDS TO TRY AND GRAB A SPOON!' }).encode()
        
    #     #try:
    #     #result = self.multicast_sock.sendto(msg, self.multicast_group)
    #     self.timeSpoonGrabbed = time.time_ns()
    #     print('2 here')
    #     # wait for responses from all players for 10s
    #     while time.time_ns() - self.timeSpoonGrabbed < 10e+9:
    #         result = self.multicast_sock.sendto(msg, self.multicast_group)

    #         print('3 here', result)
    #         try: 
    #             data, p = self.multicast_sock.recvfrom(1024)
    #             print('4 here')
    #             self.moving_forward.append(p)
    #             self.players_info[p].spoon_grabbed = 1
    #             print('received', data, 'from', p)

    #         except socket.timeout:
    #             print('too slow')


        # # notify eliminated players
        # for p in self.players:
        #     if p not in self.moving_forward:
        #         msg = json.dumps('ELIMINATED').encode()
        #         p.send(msg)
        #         self.players_info.pop(p)
        #         self.players.remove(p)
        #     else:
        #         msg = json.dumps('SPOON GRABBED. MOVING TO NEXT ROUND.').encode()
        #         p.send(msg)


        ### ? how to handle failure?
        # except Exception as e:
        #     print("FAILED", e)

    def spoons_thread(self, player, msg):
        if self.num_spoons == self.num_players - 1: # need to broadcast to everyone else to get spoon, and that first grabber got it
            self.timeSpoonGrabbed = int(msg['time'])
            self.num_spoons -= 1
            ack_msg = {'method': "grab_spoon", 'status': 'success','spoons_left': str(num_spoons)}
            response = json.dumps(response)
            player.send(response.encode())
            self.players_info[player]['spoon_grabbed'] = 1
            broadcast_msg = {'method': 'grab_spoon', 'spoons_left': str(num_spoons)}
            for p in players_info:
                if players_info[p]['spoon_grabbed'] == 0:
                    self.BroadCastQueue.append(players_info[p])
                    # need to broadcast at once.... 
        #else: # otherwise its a race condition.. might want to lock this section and make it in a thread..
            

  




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
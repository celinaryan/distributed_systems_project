import sys
import socket
import json
import os
import select
from CardDeck import *
import time
import asyncio


class SimpleUDPProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        text = data.decode("utf-8").strip()
        # May want to error check this
        response = json.loads(text)
        print(f"Received from Name Server: {response}")

class SpoonsServer:
    def __init__(self, game_name, expected_players):
        self.port                = 9000
        self.game_name           = game_name
        self.last_sent           = 0
        # TODO: Spoon count was never set?
        self.spoons              = 3
        self.BroadCastQueue      = []
        self.grab_time_stamp     = {}
        self.players             = []
        self.players_info        = {}
        self.expected_players    = expected_players
        self.num_players         = 0
        self.num_spoons          = 0
        self.deck                = CardDeck()
        self.discard_pile        = []
        self.timeSpoonGrabbed    = -1
        self.first_spoon_grabbed = 0
        self.moving_forward      = []
        # Start the name server and "master" server
        asyncio.ensure_future(self.init_server())
        asyncio.ensure_future(self.init_name_server())
        
    async def init_server(self):
        '''
        Inits the server
        '''
        self.game_init_time = time.time_ns()
        self.game_over = 0
        server = await asyncio.start_server(self.handle_client, ip, port)
        async with server:
            await server.serve_forever()

    async def handle_client(self, reader, writer):
        '''
        Handler function that runs every time a client sends something to the server. Just using client filno
        as the "new_player" you were using in your old code - can change to something else.

        TODO: Should probably add something here for if a game has already started
                1. Send a reject message to client saying a game is already in session
                2. Start another game w/ new set of clients (possible since game is running asynchronously)
        '''
        
        client_addr   = writer.get_extra_info["peername"]
        client_fileno = writer.get_extra_info["socket"].fileno()

        # Change byte amount however you set it up
        data = reader.read(1024)
        msg  = data.decode("utf-8")
        await self.execute_msg(client_fileno, client_addr, writer, msg)

    

        await writer.wait_closed()

    async def init_name_server(self):
        '''
        Initializes the name server UDP socket, setting up the transport (socket) and protocol
        '''
        loop = asyncio.get_event_loop()
        remote_addr=(socket.gethostbyname('catalog.cse.nd.edu'), 9097)
        listen = loop.create_datagram_endpoint(lambda: SimpleUDPProtocol(), remote_addr=remote_addr)
        self.transport, self.protocol = await listen

    async def init_game(self):
        # Set pickup pile of player #0 to be remaining_cards in deck object
        self.players_info[self.players[0]]['pickup_deck'] = self.deck.remaining_cards
        await self.play_game()

    async def play_game(self):
    
        while self.game_over == 0:
            if self.last_sent == 0 or time.time_ns() - self.last_sent > 6e+10:
                # Run this in the background so it doesn't get in the way of the game
                asyncio.ensure_future(self.send_udp())
            
            # either recieving message for picking up cards or spoons
            if self.first_spoon_grabbed == 0:
                ready, _, _ = select.select(self.players, [], [])
                random.shuffle(ready)   ### ??? make service more fair? is there a way to order them in the order the messages were recv'ed?
                                        # yes I think that's good
            else: # means we're in server thread

                # Don't need to do this with select
                self.broadcast("SPOON WAS GRABBED!! GRAB SPOON ASAP!")
                ready, _, _ = select.select(self.BroadCastQueue, [], [])
                self.broadcast_ready = ready
                
            # Don't need to do this with asyncio
            for player in ready:
                # player socket closed
                if player.fileno() == -1:
                    self.players.remove(player)
                    del self.players_info[player]
                    self.num_players -= 1
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
    def init_player_info(self, player, num, writer):
        self.players_info[player] = {
                                        'id': num,
                                        'writer': writer,
                                        'cards': [],
                                        'pickup_deck': [],
                                        'player_num': self.num_players,
                                        'spoon_grabbed': 0,
                                        'player_name': '',
                                        'grab_time_stamp': -1
                                    }

    async def execute_msg(self, player, player_addr, writer, msg):
        #grab_msg = { 'method': 'GRAB', 'result': '' }
        msg = json.loads(msg)
        method = msg['method']
        # TODO: handle get_cards, pickup, putdown, and spoon requests from clients
        if method == "join_game":
            # Handle if game already started...
            print(f"New Player: {player}, Address: {player_addr}")
            self.init_player_info(player, self.num_players, writer)
            self.players.append(player)
            print(f"\tPlayer {self.num_players} joined!")

            msg = { 'method': 'join_game', 'status': 'success', 'id': self.num_players }
            resp = json.dumps(msg).encode()

            # If there is an expected # of players, start running the game in the background
            self.num_players += 1
            if self.num_players  > self.expected_players:
                asyncio.ensure_future(self.init_game())

        if method == 'get_cards':
            resp = { 'method': 'get_cards', 'result': 'success', 'cards': self.players_info[player]['cards'] }

        elif method == 'pickup':
            #if self.first_spoon_grabbed:
            #    return grab_msg

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
            #if self.first_spoon_grabbed:
            #    return grab_msg

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
            # first spoon to be grabbed, enter spoon_thread for broadcast and grabbing spoon event
            if self.first_spoon_grabbed == 0:
                self.spoons_thread(self.players_info[player],msg)

    async def send_msg(self, player, msg):
        ...
            
    async def spoons_thread(self, player, msg):
        # first spoon is grabbed
        if self.num_spoons == self.num_players - 1: # need to broadcast to everyone else to get spoon, and that first grabber got it
            self.time_spoon_grabbed = float(msg["time"])
            self.num_spoons -= 1
            self.players_info[player]["spoon_grabbed"] = 1
            self.players_info[player]["grab_time_stamp"] = self.time_spoon_grabbed
            self.first_spooned_grabbed = 1
            ack_msg = {'method': "grab_spoon", 'status': 'success','spoons_left': self.num_spoons}
            response = json.dumps(ack_msg)
            self.grab_time_stamp[player] = self.time_spoon_grabbed
            await self.send_msg(player, response)
            
            tasks = []
            for p in self.players_info:
                if not self.players_info[p]["spoon_grabbed"]:
                    msg = {'method': "grab spoon"}
                    msg = json.dumps(msg)
                    tasks.append(self.send_msg(p, msg))

            await asyncio.gather(*tasks)

    async def send_msg(self, player, msg):
        writer = self.players_info[player]["writer"]
        writer.write(msg.encode())
        await writer.drain()

        #else: # otherwise its a race condition.. might want to lock this section and make it in a thread..
            
            # now we will go through ready sockets and recv messages for grabbing
            # this will recieve the message and then order the spoon grabs by time
            # then we will know who is eliminated
            #self.play_game()
    '''
            while(self.num_spoons>0):
                ready, _, _ = select.select(self.BroadCastQueue, [], [])
                self.broadcast_ready = ready
                    
                for player in ready:
                    # player socket closed
                    if player.fileno() == -1:
                        self.players.remove(player)
                        del self.players_info[player]
                        self.players -= 1
                        self.spoons -= 1
                        continue  # continue to next round
                # QUESTION: this wasnt indented, it should be right? massive block, to player.send rsp encode
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

                    method = msg['method']
                    #timeRecv = msg
                    if method == 'grab_spoon':
                        # int double or float??
                        timeGrabbed = float(msg['time'])
                        self.players_info[player]['spoon_grabbed_time'] = timeGrabbed
                        self.grab_time_stamp[player] = self.timeSpoonGrabbed
                # we will sort the dictionary of time grabs and send responses to the people who grabbed the spoons first
                sortedTimes = sorted(self.grab_time_stamp)
                if(len(sortedTimes) == self.num_spoons + 1):
                    eliminated_player = sortedTimes[-1]
                    for player in sortedTimes:
                        if player == eliminated_player:
                            response = {'result': 'eliminated'}
                            response = json.dumps(response)
                            player.send(response.encode())
                            self.players_info.pop(player)
                            self.players.remove(player)
                        else:
                            self.players_info[player]['spoon_grabbed'] = 1
                            self.num_spoons -= 1
                            response = {'result': 'next_round'}
                            response = json.dumps(response)
                            player.send(response.encode())
                else:
                    for player in sortedTimes:
                        self.players_info[player]['spoon_grabbed'] = 1
                        self.num_spoons -= 1
                        response = {'result': 'next_round'}
                        response = json.dumps(response)
                        player.send(response.encode())
        
        if(len(player_info)==1):
            self.game_over = 1
            print("Winner is Player ", self.players_info[player]['id'][0])
            return 0
        else:
            # go to next round
            self.num_players -=1
            self.start_next_round()
    '''
    # move onto the next round with eliminated player removed, one less spoon, new shuffled hands
    def start_next_round(self):
        # what we need reset at beginning of each new round
        self.BroadCastQueue = []
        self.grab_time_stamp = {}
        self.deck = CardDeck()
        self.discard_pile = []
        self.timeSpoonGrabbed = -1
        self.first_spoon_grabbed = 0
        self.remaining_cards = []
        self.deal_cards()
        self.first_spoon_grabbed = 0
        self.num_spoons = self.num_players - 1

        print("Starting next round with ", self.num_players, "players")
        for i, player in enumerate(self.players):
            self.init_player_info(player, i)
        self.init_game()
        

    def deal_cards(self):
        hands = self.deck.deal_cards(self.num_players)
        for i, player in enumerate(self.players_info.values()):
            player['cards'] = hands[i]

            
    async def send_udp(self):
        '''
        Sends a UDP message to the name server
        '''
        msg = { "type" : "hashtable", "owner" : "mnovak5", "port" : self.port, "game_name" : self.game_name }
        self.transport.sendto(json.dumps(msg).encode())
        self.last_sent = time.time_ns()

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

    #ss = SpoonsServer(game_name, num_players)

    # *******************
    #loop = asyncio.get_event_loop()
    ss = SpoonsServer(game_name, num_players)
    # *******************
    #server = Server(sys.argv[1], sys.argv[2], loop)
    #ss.start_server()
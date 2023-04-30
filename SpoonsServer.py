import sys
import socket
import json
import os
import select
from CardDeck import *
import time
import asyncio
from BroadCast import * 

class SpoonsServer:
    def __init__(self, game_name, expected_players, loop: asyncio.AbstractEventLoop):
        self.master = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.name_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.port = 9000
        self.game_name = game_name
        self.last_sent = 0
        self.BroadCastQueue = []
        self.grab_time_stamp = {}
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

        # *******************
        # added asynchio stuff
        self.__ip: str = self.socket.gethostname()
        self.__port: int = self.port
        self.__loop: asyncio.AbstractEventLoop = loop
        self.__logger: logging.Logger = self.initialize_logger()
        self.__clients: dict[asyncio.Task, Client] = {}

        self.logger.info(f"Server Initialized with {self.host}:{self.port}")
        # *******************

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
                # new_player is:
                # <socket.socket fd=5, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0, laddr=('129.74.152.140', 9000), raddr=('129.74.152.141', 54564)>
                # addr is:
                # address:  ('129.74.152.141', 54564)
                (new_player, addr) = self.master.accept()
                print("new player: ", new_player, "address: ", addr)
                #print()
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
                self.init_game() 

            #### send winner message to the winning player 
        # *******************
        # asyncio stuff
        @property
        def ip(self):
            return self.__ip

        @property
        def port(self):
            return self.__port

        @property
        def loop(self):
            return self.__loop

        @property
        def logger(self):
            return self.__logger

        @property
        def clients(self):
            return self.__clients

    def initialize_logger(self):
        '''
        Initializes a logger and generates a log file in ./logs.
        Returns
        ——-
        logging.Logger
            Used for writing logs of varying levels to the console and log file.
        ——-
        '''
        path = pathlib.Path(os.path.join(os.getcwd(), "logs"))
        path.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger('Server')
        logger.setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        fh = logging.FileHandler(
            filename=f'logs/{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}_server.log'
        )
        ch.setLevel(logging.INFO)
        fh.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            '[%(asctime)s] – %(levelname)s – %(message)s'
        )

        ch.setFormatter(formatter)
        fh.setFormatter(formatter)
        logger.addHandler(ch)
        logger.addHandler(fh)

        return logger
    
    def start_server(self):
        '''
        Starts the server on IP and PORT.
        '''
        try:
            self.server = asyncio.start_server(
                self.accept_client, self.host, self.port
            )
            self.loop.run_until_complete(self.server)
            self.loop.run_forever()
        except Exception as e:
            self.logger.error(e)
        except KeyboardInterrupt:
            self.logger.warning("Keyboard Interrupt Detected. Shutting down!")

        self.shutdown_server()
    
    def accept_client(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter):
        '''
        Callback that is used when server accepts clients
        Parameters
        ———-
        client_reader : asyncio.StreamReader
            StreamReader generated by asyncio.start_server.
        client_writer : asyncio.StreamWriter
            StreamWriter generated by asyncio.start_server.
        ———-
        '''
        client = Client(client_reader, client_writer)
        task = asyncio.Task(self.handle_client(client))
        self.clients[task] = client

        client_ip = client_writer.get_extra_info('peername')[0]
        client_port = client_writer.get_extra_info('peername')[1]
        self.logger.info(f"New Connection: {client_ip}:{client_port}")

        task.add_done_callback(self.disconnect_client)
    
    async def handle_client(self, client: Client):
        '''
        Handles incoming messages from client
        Parameters
        ———-
        client_reader : asyncio.StreamReader
            StreamReader generated by asyncio.start_server.
        client_writer : asyncio.StreamWriter
            StreamWriter generated by asyncio.start_server.
        ———-
        '''
        while True:
            client_message = await client.get_message()

            if client_message.startswith("quit"):
                break
            elif client_message.startswith("/"):
                self.handle_client_command(client, client_message)
            else:
                self.broadcast_message(
                    f"{client.nickname}: {client_message}".encode('utf8'))

            self.logger.info(f"{client_message}")

            await client.writer.drain()

        self.logger.info("Client Disconnected!")

    def handle_client_command(self, client: Client, client_message: str):
        client_message = client_message.replace("\n", "").replace("\r", "")

        if client_message.startswith("/nick"):
            split_client_message = client_message.split(" ")
            if len(split_client_message) >= 2:
                client.nickname = split_client_message[1]
                client.writer.write(
                    f"Nickname changed to {client.nickname}\n".encode('utf8'))
                return

        client.writer.write("Invalid Command\n".encode('utf8'))

    def broadcast_message(self, message: bytes, exclusion_list: list = []):
        '''
        Parameters
        ———-
        message : bytes
            A message consisting of utf8 bytes to broadcast to all clients.
        OPTIONAL exclusion_list : list[Client]
            A list of clients to exclude from receiving the provided message.
        ———-
        '''
        for client in self.clients.values():
            if client not in exclusion_list:
                client.writer.write(message)
    
    def disconnect_client(self, task: asyncio.Task):
        '''
        Disconnects and broadcasts to the other clients that a client has been disconnected.
        Parameters
        ———-
        task : asyncio.Task
            The task object associated with the client generated during self.accept_client()
        ———-
        '''
        client = self.clients[task]

        self.broadcast_message(
            f"{client.nickname} has left!".encode('utf8'), [client])

        del self.clients[task]
        client.writer.write('quit'.encode('utf8'))
        client.writer.close()
        self.logger.info("End Connection")

    def shutdown_server(self):
        '''
        Shuts down server.
        '''
        self.logger.info("Shutting down server!")
        for client in self.clients.values():
            client.writer.write('quit'.encode('utf8'))
        self.loop.stop()
    # *******************

    def init_game(self):
        # Set pickup pile of player #0 to be remaining_cards in deck object
        self.players_info[self.players[0]]['pickup_deck'] = self.deck.remaining_cards
        self.play_game()

    def play_game(self):

        # moved initilization to function called init_game so we can interleave grabbing 
        # spoon messages also
    
        while self.game_over == 0:
            if self.last_sent == 0 or time.time_ns() - self.last_sent > 6e+10:
                self.send_udp()
                self.last_sent = time.time_ns()
            
            # either recieving message for picking up cards or spoons
            if self.first_spoon_grabbed == 0:
                ready, _, _ = select.select(self.players, [], [])
                random.shuffle(ready)   ### ??? make service more fair? is there a way to order them in the order the messages were recv'ed?
                                        # yes I think that's good
            else: # means we're in server thread
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
                                        'player_name': '',
                                        'grab_time_stamp': -1
                                    }

    def execute_msg(self, player, msg):
        #grab_msg = { 'method': 'GRAB', 'result': '' }
        msg = json.loads(msg)
        method = msg['method']

        # TODO: handle get_cards, pickup, putdown, and spoon requests from clients
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
        # first spoon is grabbed
        if self.num_spoons == self.num_players - 1: # need to broadcast to everyone else to get spoon, and that first grabber got it
            self.timeSpoonGrabbed = float(msg['time'])
            self.num_spoons -= 1
            ack_msg = {'method': "grab_spoon", 'status': 'success','spoons_left': str(num_spoons)}
            response = json.dumps(response)
            player.send(response.encode())
            self.players_info[player]['spoon_grabbed'] = 1
            self.players_info[player]['grab_time_stamp'] = self.timeSpoonGrabbed 
            self.first_spoon_grabbed = 1
            #broadcast_msg = {'method': 'grab_spoon', 'spoons_left': str(num_spoons)}
            self.grab_time_stamp[player] = self.timeSpoonGrabbed
            for p in players_info:
                if players_info[p]['spoon_grabbed'] == 0:
                    self.BroadCastQueue.append(players_info[p])
                    #asyncio.run(tcp_echo_client('GRAB SPOON!'))
                    # need to broadcast at once.... '
            broadcast = BroadCast(self.BroadCastQueue)
        #else: # otherwise its a race condition.. might want to lock this section and make it in a thread..
            
            # now we will go through ready sockets and recv messages for grabbing
            # this will recieve the message and then order the spoon grabs by time
            # then we will know who is eliminated
            #self.play_game()
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

    #ss = SpoonsServer(game_name, num_players)

    # *******************
    loop = asyncio.get_event_loop()
    ss = SpoonsServer(game_name, num_players, loop)
    # *******************
    #server = Server(sys.argv[1], sys.argv[2], loop)
    #ss.start_server()
    
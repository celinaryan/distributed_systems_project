import asyncio
import logging
import socket
import json
log = logging.getLogger(__name__)

clients = {}  # task -> (reader, writer)
SERVER = 'student10.cse.nd.edu'
PORT = '9000'
class Server2:
#    def __init__(self, game_name):
    def __init__(self, game_name, expected_players):
        self.master = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.port = PORT
        self.game_name = game_name
        self.host = SERVER
        self.last_sent = 0
        self.BroadCastQueue = []
        self.grab_time_stamp = {}

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
        self.clients = {}

        self.init_loop()

        # for port already used error
        for i in range(1,15):
        try:
            self.master.bind((socket.gethostname(), self.port))
            break
        except:
            self.port += 1

        while True:
            if self.last_sent == 0 or time.time_ns() - self.last_sent > 6e+10:
                self.send_udp(self.game_name, "SpoonsServer")
                self.last_sent = time.time_ns()

            print('Game loading...')

            while self.num_players < self.expected_players:
                (new_player, addr) = self.master.accept()
                print("new player: ", new_player, "address: ", addr)
                #print()
                self.players.append(new_player)
                self.init_player_info(new_player, self.num_players)
                print('\tPlayer', self.num_players, 'joined!')
                msg = { 'method': 'join_game', 'status': 'success', 'id': self.num_players }
                resp = json.dumps(msg).encode()
                new_player.send(resp)
                self.num_players += 1
                self.game_init_time = time.time_ns()
        
        while self.num_players > 1:
            print('Starting game!')
            self.init_game() 
    # initialize async loop / connection
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
        #if self.last_sent == 0 or time.time_ns() - self.last_sent > 6e+10:
        send_udp(self.game_name, "AsyncServer")
            #self.last_sent = time.time_ns()
        loop = asyncio.get_event_loop()
        f = asyncio.start_server(accept_client, host=SERVER, port=PORT)
        loop.run_until_complete(f)
        loop.run_forever()

    def init_game(self):
        # Set pickup pile of player #0 to be remaining_cards in deck object
        self.players_info[self.players[0]]['pickup_deck'] = self.deck.remaining_cards
        self.play_game()

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
    
    def play_game(self):

        # moved initilization to function called init_game so we can interleave grabbing 
        # spoon messages also
        while self.game_over == 0:
            if self.last_sent == 0 or time.time_ns() - self.last_sent > 6e+10:
                self.send_udp(self.game_name, "SpoonsServer")
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
                                        'grab_time_stamp': -1,
                                        'writer': ''
                                    }
    def deal_cards():
        hands = self.deck.deal_cards(self.num_players)
        for i, player in enumerate(self.players_info.values()):
            player['cards'] = hands[i]
            currWriter = player['writer']
            writer.write(json.dumps({'method':'get_cards', 'cards': player['cards']}).encode())
            asynchio.create_task(currWriter.drain())
        # where's the leftover deck?

    def accept_client(client_reader, client_writer):
        task = asyncio.Task(handle_client(client_reader, client_writer))
        clients[task] = (client_reader, client_writer)

        def client_done(task):
            del clients[task]
            client_writer.close()
            log.info("End Connection")

        log.info("New Connection")
        task.add_done_callback(client_done)

    def send_udp(self, game_name, serverName):
        name_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = { "type" : "hashtable", "owner" : "mnovak5", "port" : self.port, "game_name" : game_name, "serverName": serverName}
        result = name_server.sendto(json.dumps(msg).encode(), (socket.gethostbyname('catalog.cse.nd.edu'), 9097))

        while(result == -1):
            self.last_sent = time.time_ns()
            msg = { "type" : "hashtable", "owner" : "mnovak5", "port" : self.port, "game_name" : game_name, "serverName": serverName }
            result = name_server.sendto(json.dumps(msg).encode(), (socket.gethostbyname('catalog.cse.nd.edu'), 9097))

        name_server.close()

async def handle_client(reader, writer):
    # send a hello to let the client know they are connected
    print("New Player connected")
    writer.write("Let's play spoons!").encode()
    await writer.drain()

    self.deck = self.deal_cards()
    
    self.clients[writer] = None
    while True:
        data = await reader.readline()
        if not data:
            break
        # send message to spcific client
        for writer, client_id in self.client.items():
            if client_id == 0:
                writer.write(data)
                await writer.drain()
    del clients[writer]
    writer.close()


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
        #await self.broadcast()
        print("BROADCAST HERE")
        self.send_to_all_clients(client_reader,client_writer, "GRAB SPOON")


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
    ss = Server2(game_name, num_players)
import sys
import socket
import json
import http.client
import time
import asyncio
from functools import partial
from concurrent.futures.thread import ThreadPoolExecutor

class SpoonException(Exception):
	pass

# hard coded server address for now
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
		self.id = -1
		self.grabbing_started = 0
		self.eliminated = 0
		self.reader = None
		self.writer = None
		self.host = None

		self.mycards = []
		
	async def run(self):
		await self.connect_to_server()
		# Read for the start of the game
		resp = await self.recv_resp({"dummy": "dummy"})
		if resp['method'] == 'start_game':
			print("Game is starting")
			await self.play_game()

	async def listen(self, port, ip):
		loop = asyncio.get_event_loop()
		remote_addr=('0.0.0.0', 9004)
		listen = loop.create_datagram_endpoint(lambda: SimpleUDPProtocol(), remote_addr=remote_addr)
		self.transport, self.protocol = await listen
		#asyncio.ensure_future(self.play_game())			


	def find_name(self):
		#'finding name')
		while (True):
			name_server = http.client.HTTPConnection('catalog.cse.nd.edu', '9097')
			name_server.request('GET', '/query.json')
			name_server_entries = json.loads(name_server.getresponse().read().decode())
			#print("Got entry from name server")

			for entry in name_server_entries:
				try:
					if self.host == None and entry['game_name'] == self.game_name: # save the first match
						self.host = entry['host']
						self.port = entry['port']
						self.lastheardfrom = entry['lastheardfrom']

					elif entry['game_name'] == self.game_name:   # if exist more matches --> check lastheardfrom
						if entry['lastheardfrom'] > self.lastheardfrom:
							self.host = entry['host']
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

	async def connect_to_server(self):
		#TODO: Set timeout
		self.find_name()
		#print(f"Found name: {self.game_name} at {self.host}:{self.port}")

		self.server_retries = 0
		# while True:
		#     try:
		self.reader, self.writer = await asyncio.open_connection(self.host, int(self.port))
		#print("connected to server")
		msg = {'method': 'join_game'}
		msg = json.dumps(msg)
		await self.send_request(msg)
		resp = await self.recv_resp(msg)
		self.id = int(resp['id'])
		#print('Connected to port: ', self.port)
		print('Welcome! You are player ' + str(self.id) + '!')
		if self.id == 0:
			print('\nYou are the first player in the circle! You will be picking up from the remaining deck and will begin the flow of cards.')
		# break
			# except Exception as e:
			#     print(f'Connection to server failed. Restarting connection: {e}')
			#     self.find_name()
			#     time.sleep(2**self.server_retries)
			#     self.server_retries+=1
		
	async def get_user_input(self):
		return await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)


	async def play_game(self):
		print(f"Starting game..")
		await self.get_cards()
		#get_input = partial(asyncio.get_event_loop().run_in_executor, ThreadPoolExecutor(1))
		spoon_listen = partial(asyncio.get_event_loop().run_in_executor, ThreadPoolExecutor(1))

		while(self.grabbing_started == 0):

			print('\nYOUR HAND:')
			self.display_cards(self.mycards, 1)

			#spoon_listen = asyncio.ensure_future(self.wait_on_broadcast())
			spoon_notif = await spoon_listen(self.wait_on_broadcast)
			#get_input = asyncio.get_event_loop().run_in_executor(ThreadPoolExecutor(1), input, "Enter 'p' to pickup next card\nEnter 'x' to try to grab a spoon\n")
			method = await asyncio.open_stdin().readline()
			method = method.strip()
				

			#spoon_notif = await self.listen()
			#print('NOTIF:',spoon_notif)
			#spoon_notif = await spoon_listen(self.wait_on_broadcast())
			#if not spoon_notif:


			if method != 'p' and method != 'x':
				print('Invalid operation')
				continue
			if method == 'x':
				await self.grab_spoon()
			if method == 'p':
				new_card = await self.pickup()
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

				ind = await get_input(input, "\tEnter card to discard (0-4): ")

				while ind not in ['0', '1', '2', '3', '4']:
					print('\tInvalid card selected.')
					ind = await get_input(input, "\tEnter card to discard (0-4): ")
				ind = int(ind)
				discard_card = self.mycards[ind]
				resp = await self.discard(discard_card)
				if resp == 'next_round' or resp == 'eliminated':
					return
				self.mycards.remove(discard_card)
			sys.stdout.flush()
		#else:
			#await self.grab_spoon()

	
	async def wait_on_broadcast(self):
		msg = { 'method': 'want_broadcast'}
		msg = json.dumps(msg)
		await self.send_request(msg)
		resp = await self.recv_resp(msg)
		if resp['method'] =='grab spoon':
			return 1
		else:
			return 0
	

	async def grab_spoon(self):
		get_input = partial(asyncio.get_event_loop().run_in_executor, ThreadPoolExecutor(1))

		print("Are you ready to grab a spoon?")
		wantSpoon = await get_input(input, "ENTER x TO GRAB SPOON! ")
		# user gets correct card line up and grabs spoon
		if wantSpoon.strip() == 'x':
			# first person to grab spoon
			if self.four_of_a_kind() and self.grabbing_started == 0:
				self.grabbing_started = 1
				t = time.time_ns()
				msg = { 'method': 'grab_spoon','time': str(t)}
				msg = json.dumps(msg)
				await self.send_request(msg)
				
				resp = await self.recv_resp(msg)
				status = resp['status']
				if status == 'success':
					if resp['spoons_left'] == 0:
						print("You got the last spoon. You win!!")
					else:
						print("You successfully grabbed a spoon!\nWait for the other players to grab the spoons for the next round.")
			elif self.four_of_a_kind() == 0 and self.grabbing_started == 0:
				print("\nInvalid cards to grab spoon. Keep playing!")
				return
			elif self.grabbing_started == 1:
				msg = { 'method': 'grab_spoon','time': str(t)}
				msg = json.dumps(msg)
				await self.send_request(msg)

				resp = await self.recv_resp(msg)
				server_ack = json.loads(resp.decode())

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
			if(self.grabbing_started==1):
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
		
	   

	async def get_cards(self):
		msg = { 'method': 'get_cards' }
		msg = json.dumps(msg)
		await self.send_request(msg)
		resp = await self.recv_resp(msg)
		self.mycards = resp['cards']

	async def pickup(self):
		msg = { 'method': 'pickup' }
		msg = json.dumps(msg)
		await self.send_request(msg)
		resp = await self.recv_resp(msg)
		#print(f"Tried to pick up a new card, got response: {resp}")
		#if resp['method'] == 'GRAB':
			# self.grabbing_started = 1
			# x = input('GRABBING STARTED!\n\tENTER x TO GRAB! : ')
			# return self.grab_spoon()
		
		#print('RESP:', resp)
		if resp['result'] == 'success':
			#print(f"Got card: {resp['card']}")
			return resp['card']
		else:
			return None

	async def discard(self, card):
		print("HERE HERE")
		msg = { 'method': 'discard', 'card': card}
		msg = json.dumps(msg)
		await self.send_request(msg)
		resp = await self.recv_resp(msg)
		#if resp['method'] == 'GRAB':
		#    self.grabbing_started = 1
		#    x = input('GRABBING STARTED!\n\tENTER x TO GRAB!')
		#    return self.grab_spoon()
		return None
  
	async def send_request(self, msg):
		#print(f"Sending message: {msg}")
		length = str(len(msg)).encode()
		msg = msg.encode()
		self.writer.write(length + msg)
		await self.writer.drain()
		# self.send_retries = 0
		# bytes_sent = 0
		# while(True):
		#     try:
		#         self.writer.write(str(len(msg.encode())).encode() + msg.encode())
		#         bytes_sent = self.s.send(str(len(msg.encode())).encode() + msg.encode())
		#     except Exception as e:
		#         print('Connection to server lost. Restarting connection.')
		#         self.s.close()
		#         self.connect_to_server()
		#         continue

		#     if bytes_sent == 0:
		#         print('Failed to send request to server. Restarting connection.')
		#         self.s.close()
		#         self.connect_to_server()
		#         time.sleep(2**self.send_retries)
		#         self.send_retries+=1
		#     else:
		#         break

	async def recv_resp(self, msg):
		# self.recv_retries = 0
		# bytes_recv = 0

		# while(True):
		#     try:
		#         resp = json.loads(self.s.recv(4096).decode())
		#     except Exception as e:
		#         print('Connection lost. Restarting connection.')
		#         self.s.close()
		#         self.connect_to_server()
		#         self.send_request(msg)
		#         continue

		#     if len(resp) == 0 or resp == -1:
		#         print('Failed to receive response from server. Restarting connection.')
		#         self.s.close()
		#         self.connect_to_server()
		#         self.send_request(msg)
		#         time.sleep(2**self.recv_retries)
		#         self.recv_retries+=1
		#     else:
		#         break
		data = await self.reader.read(4096)
		resp = json.loads(data.decode())
		#print(f"Got response: {resp}")
		return resp

	def four_of_a_kind(self):
		if self.mycards[0][:-1] == self.mycards[1][:-1] == self.mycards[2][:-1] == self.mycards[3][:-1]:
			return 1
		return 0


	def display_cards(self, cards, graphics):
		#print(f"My cards: {cards}")
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
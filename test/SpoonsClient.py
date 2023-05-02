import asyncio
import socket
import struct
import sys

BROADCAST_PORT = 1910
BROADCAST_ADDR = "239.255.255.250"
#BROADCAST_ADDR = "ff0e::10"

class SpoonsClient:
    def __init__(self, loop, addr):
        self.loop = loop
        self.transport = None
        self.addr = addr

    def connection_made(self, transport):
        self.transport = transport
        sock = self.transport.get_extra_info('socket')
        sock.settimeout(3)
        addrinfo = socket.getaddrinfo(self.addr, None)[0]
        if addrinfo[0] == socket.AF_INET: # IPv4
            ttl = struct.pack('@i', 1)
            sock.setsockopt(socket.IPPROTO_IP, 
                socket.IP_MULTICAST_TTL, ttl)
        else:
            ttl = struct.pack('@i', 2)
            sock.setsockopt(socket.IPPROTO_IPV6, 
                socket.IPV6_MULTICAST_HOPS, ttl)

        self.transport.sendto(sys.argv[1].encode("ascii"), (self.addr,BROADCAST_PORT))

    def datagram_received(self, data, addr):
        print("Reply from {}: {!r}".format(addr, data))
        # Don't close the socket as we might get multiple responses.

    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self, exc):
        print("Socket closed, stop the event loop")
        self.loop.stop()


loop = asyncio.get_event_loop()

addrinfo = socket.getaddrinfo(BROADCAST_ADDR, None)[0]
sock = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
connect = loop.create_datagram_endpoint(
    lambda: SpoonsClient(loop,BROADCAST_ADDR),
    sock=sock,
)
transport, protocol = loop.run_until_complete(connect)
loop.run_forever()
transport.close()
loop.close()
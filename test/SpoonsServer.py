import asyncio
import logging
import socket
import struct

BROADCAST_PORT = 1910
BROADCAST_ADDR = "239.255.255.250"
#BROADCAST_ADDR = "ff0e::10"

class SpoonsServer:

    def connection_made(self, transport):
        self.transport = transport


    def datagram_received(self, data, addr):
        print('Received {!r} from {!r}'.format(data, addr))
        data = "I received {!r}".format(data).encode("ascii")
        print('Send {!r} to {!r}'.format(data, addr))
        self.transport.sendto(data, addr)
    def PlaySpoons(self):
        print("play Spoons")
    
if __name__=='__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(SpoonsServer.PlaySpoons(loop=loop))
    loop.set_debug(True)
    logging.basicConfig(level=logging.DEBUG)

    addrinfo = socket.getaddrinfo(BROADCAST_ADDR, None)[0]
    sock = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    group_bin = socket.inet_pton(addrinfo[0], addrinfo[4][0])
    if addrinfo[0] == socket.AF_INET: # IPv4
        sock.bind(('', BROADCAST_PORT))
        mreq = group_bin + struct.pack('=I', socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    else:
        sock.bind(('', BROADCAST_PORT))
        mreq = group_bin + struct.pack('@I', 0)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)


    listen = loop.create_datagram_endpoint(
        SpoonsServer,
        sock=sock,
    )
    transport, protocol = loop.run_until_complete(listen)

    loop.run_forever()
    loop.close()
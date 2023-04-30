import sys
import asyncio
from SpoonsClient import SpoonsClient
class ClientAsync:
    def __init__(self, game_name, host, port):
    #def main(id=None, myport=None, ip=None, port=None):
        self.ClientInstance = SpoonsClient(game_name)
        self.game_name = game_name
        self.port = port
        self.host = host
        self.loopDone = 0
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # check this number, why 10,000?
        loop.run_until_complete(self.ClientInstance.listen(10_000))
        loop.run_until_complete(self.ClientInstance.bootstrap([(self.host, self.port)]))
        loop.run_until_complete(shell(self.ClientInstance))
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.ClientInstance.stop()
            loop.close()
            self.loopDone = 1
            return self.loopDone
        
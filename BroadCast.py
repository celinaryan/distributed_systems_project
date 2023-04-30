import sys
import asyncio
class BroadCast:
    def __init__(self, BroadCastQueue):
        self.message = asyncio.Future()
        self.BroadCastQueue = BroadCastQueue

    async def run(self):
        while True:
            await asyncio.sleep(1.0)
            self.message.set_result(b'SPOON WAS GRABBED!! GRAB SPOON ASAP!')
            self.message = asyncio.Future()

    async def async_handler(self, name, message_generator):
        while True:
            message = await asyncio.shield(message_generator.message)
            print(name, message)

    async def async_main(self):
        message_generator = BroadCast()
        asyncio.create_task(message_generator.run())
        # not sure if "name" param is right because p is technically the socket info...
        for p in self.BroadCastQueue:
            asyncio.create_task(async_handler(p, message_generator))
            await asyncio.sleep(10.0)
    
if __name__ == "__main__":
    asyncio.run(self.async_main())
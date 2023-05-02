from SpoonsClient import *
import sys
import asyncio

async def main():
    if len(sys.argv) != 2:
        print('Invalid number of arguments')
        print('Usage: python3 PlaySpoons.py <GAME_NAME>')
        exit(1)
    else:
        game_name = sys.argv[1]

    player = SpoonsClient(game_name)
    #while(not eliminated):
    
    await asyncio.gather(player.play_game(), player.monitor_spoons())

if __name__=='__main__':
    asyncio.run(main())
    
from SpoonsClient import *
import sys
if __name__=='__main__':
    if len(sys.argv) != 3:
        print('Invalid number of arguments')
        print('Usage: python3 PlaySpoons.py <GAME_NAME> <PLAYER_NAME>')
        exit(1)
    else:
        game_name = sys.argv[1]
        player_name = sys.argv[2]

    player = SpoonsClient(game_name, player_name)
    
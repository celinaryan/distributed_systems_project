from SpoonsClient import *

if __name__=='__main__':
    if len(sys.argv) != 2:
        print('Invalid number of arguments')
        print('Usage: python3 PlaySpoons.py <GAME_NAME>')
        exit(1)
    else:
        game_name = sys.argv[1]

    player = SpoonsClient(game_name)
    
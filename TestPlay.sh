#!/bin/bash
echo 'start'
date +%s.%N

    python3 PlaySpoons.py spoons-game < testInput.txt

date +%s.%N
echo 'end'
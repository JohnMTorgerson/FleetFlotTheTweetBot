#!/bin/bash

export PATH=~/.pyenv/shims:~/.pyenv/bin:"$PATH"

echo 'running FleetFlot'
cd "$HOME"/Projects/FleetFlotTheTweetBot
python main.py

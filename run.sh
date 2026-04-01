#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

pip install -e . -q

if [ ! -f "booru.conf" ]; then
    echo "Creating config file from template..."
    cp booru.conf.example booru.conf
    echo "⚠️  Edit booru.conf with your API keys, then run this script again!"
    exit 1
fi

python -m booruswipe --verbose

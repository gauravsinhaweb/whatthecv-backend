#!/bin/bash

# Function to display usage
show_usage() {
    echo "Usage: ./run.sh [OPTION]"
    echo "Options:"
    echo "  start     Start the application (default)"
    echo "  setup     Set up virtual environment and install dependencies"
    echo "  help      Show this help message"
}

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Process command line arguments
case "$1" in
    start|"")
        echo "Starting WhatTheCV..."
        
        # If venv exists, activate it
        if [ -d "venv" ]; then
            source venv/bin/activate 2>/dev/null || source venv/Scripts/activate
        fi
        
        # Run the application with the start script
        python start.py
        ;;
    setup)
        echo "Setting up WhatTheCV..."
        
        # Create virtual environment if it doesn't exist
        if [ ! -d "venv" ]; then
            echo "Creating virtual environment..."
            python3 -m venv venv
        fi
        
        # Activate virtual environment
        source venv/bin/activate 2>/dev/null || source venv/Scripts/activate
        
        # Install dependencies
        echo "Installing dependencies..."
        pip install --upgrade pip
        pip install -r requirements.txt
        
        # Run the setup part of our start script
        python start.py --setup-only
        
        echo "Setup complete! Run './run.sh start' to start the application."
        ;;
    help)
        show_usage
        ;;
    *)
        echo "Unknown option: $1"
        show_usage
        exit 1
        ;;
esac 
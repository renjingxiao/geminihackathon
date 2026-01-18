#!/bin/bash

echo "======================================================================"
echo "PMM System - Quick Start Script"
echo "======================================================================"
echo

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: Please run this script from the pmm_system directory"
    exit 1
fi

# Step 1: Install dependencies
echo "Step 1: Installing dependencies..."
pip install -r requirements.txt -q
if [ $? -eq 0 ]; then
    echo "✓ Dependencies installed"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo

# Step 2: Run demo
echo "Step 2: Running demo..."
echo "Press CTRL+C to stop the demo at any time"
echo
python scripts/demo.py

# Step 3: Offer to start API server
echo
echo "======================================================================"
echo "Demo completed!"
echo "======================================================================"
echo
echo "Would you like to start the API server? (y/n)"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    echo
    echo "Starting API server..."
    echo "API will be available at: http://localhost:8000"
    echo "API docs at: http://localhost:8000/docs"
    echo
    echo "Press CTRL+C to stop the server"
    echo
    python -m pmm_agent.main
else
    echo
    echo "To start the API server manually, run:"
    echo "  python -m pmm_agent.main"
    echo
    echo "To test the API, run:"
    echo "  python scripts/test_client.py"
    echo
fi

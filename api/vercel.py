from fastapi import FastAPI, Request
import sys
import os

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the app from index.py
from api.index import app

# This is needed for Vercel serverless functions
def handler(request, context):
    return app(request) 
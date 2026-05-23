#!/bin/bash
# Start script for Render - explicitly uses uvicorn
exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --loop uvloop

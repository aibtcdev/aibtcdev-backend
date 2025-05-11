#!/usr/bin/env python
"""Docker entrypoint script to run the application."""

import os
import sys

# Add the current directory to the path
sys.path.insert(0, os.path.abspath("."))

# Run uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)

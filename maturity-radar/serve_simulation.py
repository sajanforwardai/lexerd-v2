#!/usr/bin/env python3
"""
Simple HTTP server to serve the Goldman Sachs TMT Simulation HTML file
Runs on port 8507 to avoid conflict with Streamlit (8506)
"""

import http.server
import socketserver
import os

PORT = 8507
HANDLER = http.server.SimpleHTTPRequestHandler

# Change to the directory where the HTML file is located
os.chdir(os.path.dirname(os.path.abspath(__file__)))

with socketserver.TCPServer(("", PORT), HANDLER) as httpd:
    print(f"✓ Simulation server running at http://localhost:{PORT}/gs_simulation.html")
    print(f"✓ Public URL: https://forwardai.dev:8507/gs_simulation.html")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Server stopped")

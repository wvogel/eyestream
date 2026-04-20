"""Shared test configuration and fixtures."""
import sys
import os

# Make the app/ directory importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

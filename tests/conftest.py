"""Shared test configuration and fixtures."""
import sys
import os
from unittest import mock

# Prevent StaticFiles from failing when /app/static doesn't exist locally
sys.modules["fastapi.staticfiles"] = mock.MagicMock()

import sys
from pathlib import Path

# Add project root to sys.path so it works directly from CLI
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

"""Bridge between Python and Rust implementations"""
import subprocess
import json
import sys
import os
from pathlib import Path

class RustBridge:
    """Handles calling Rust CLI from Python when available"""
    
    def __init__(self):
        self.rust_binary = self._find_rust_binary()
    
    def _find_rust_binary(self):
        """Look for compiled Rust binary"""
        possible_paths = [
            Path("target/release/kubelingo"),
            Path("target/debug/kubelingo"),
            Path("./kubelingo-rust")
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        return None
    
    def is_available(self):
        # Allow disabling Rust integration via environment variable
        if os.getenv("KUBELINGO_DISABLE_RUST", "").lower() in ("1", "true", "yes"):
            return False
        return self.rust_binary is not None
    
    def run_pty_shell(self) -> bool:
        """Delegate PTY shell spawning to Rust CLI if available"""
        if not self.is_available():
            return False
        cmd = [self.rust_binary, "pty"]
        try:
            result = subprocess.run(cmd)
            return result.returncode == 0
        except Exception:
            return False

# Global bridge instance
rust_bridge = RustBridge()

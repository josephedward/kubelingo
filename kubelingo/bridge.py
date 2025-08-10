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
        # Disable Rust integration by default to ensure Python fallback and avoid external binary execution
        return False
    
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

    def run_command_quiz(self, args) -> bool:
        """Delegate command quiz to Rust CLI if available."""
        if not self.is_available():
            return False

        cmd = [self.rust_binary, "k8s", "quiz"]

        if hasattr(args, 'num') and args.num is not None and args.num > 0:
            cmd.extend(["--num", str(args.num)])

        if hasattr(args, 'category') and args.category:
            cmd.extend(["--category", args.category])

        try:
            # The Rust app will take over the terminal
            result = subprocess.run(cmd)
            return result.returncode == 0
        except Exception:
            return False


# Global bridge instance
rust_bridge = RustBridge()

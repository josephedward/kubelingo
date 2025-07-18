import os
import subprocess
import time
import tempfile

class VimrunnerException(Exception):
    pass

class Client(object):
    """Client to control a Vim server instance."""
    def __init__(self, server):
        self.server = server

    def type(self, keys):
        """Send keystrokes to the Vim server."""
        cmd = self.server.executable + ['--servername', self.server.name, '--remote-send', keys]
        subprocess.check_call(cmd)
        # Allow Vim time to process the keys.
        time.sleep(0.1)

    def command(self, command):
        """Execute an Ex command in Vim."""
        # Use --remote-expr to execute a command and get output.
        remote_expr = f"execute('{command}')"
        cmd = self.server.executable + ['--servername', self.server.name, '--remote-expr', remote_expr]
        return subprocess.check_output(cmd, universal_newlines=True)

    def write(self):
        """Write the current buffer to file."""
        self.type('<Esc>:w<CR>')


class Server(object):
    """Starts and manages a Vim server process."""
    def __init__(self, executable='vim'):
        self.executable = [executable]
        # Generate a unique server name to avoid conflicts
        self.name = f"KUBELINGO-TEST-{os.getpid()}"
        self.process = None

    def start(self, file_to_edit=None):
        """Starts the Vim server in the background."""
        # Use --nofork to keep gvim process in the foreground for Popen to manage
        cmd = self.executable + ['--servername', self.name]
        # --nofork is a gvim-specific flag, not applicable to terminal vim
        if 'gvim' in self.executable[0] or 'mvim' in self.executable[0]:
            cmd.append('--nofork')
            
        if file_to_edit:
            cmd.append(file_to_edit)

        self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait for the server to initialize by polling --serverlist.
        for _ in range(20):  # Try for 2 seconds
            time.sleep(0.1)
            try:
                serverlist = subprocess.check_output(self.executable + ['--serverlist'], text=True, stderr=subprocess.DEVNULL)
                if self.name in serverlist.splitlines():
                    return Client(self)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # This can happen if vim is starting up.
                continue

        # If server did not start, clean up and raise error.
        self.kill()
        raise VimrunnerException(f"Failed to start Vim server '{self.name}'.")

    def kill(self):
        """Stops the Vim server process."""
        if self.process:
            # First, try a graceful shutdown using a remote command
            try:
                cmd = self.executable + ['--servername', self.name, '--remote-expr', 'execute("qa!")']
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # If graceful shutdown fails, terminate the process
                self.process.terminate()

            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()  # Force kill if it doesn't terminate

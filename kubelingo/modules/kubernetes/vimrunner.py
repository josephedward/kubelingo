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
        cmd = self.executable + ['--servername', self.name]
        if file_to_edit:
            cmd.append(file_to_edit)
        
        self.process = subprocess.Popen(cmd)
        
        # Wait for the server to initialize. A more robust implementation
        # would poll `vim --serverlist`.
        time.sleep(1)

        return Client(self)

    def kill(self):
        """Stops the Vim server process."""
        if self.process:
            try:
                # Politely ask Vim to quit
                cmd = self.executable + ['--servername', self.name, '--remote-expr', 'execute("q!")']
                subprocess.check_call(cmd, stderr=subprocess.PIPE)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # If Vim is already gone or command fails, forcefully kill.
                self.process.kill()
            self.process.wait()

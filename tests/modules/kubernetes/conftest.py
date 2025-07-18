import pytest
import shutil
import subprocess

@pytest.fixture(scope="session")
def vim_executable():
    """
    Finds a vim executable with +clientserver support.
    
    Checks for 'gvim', 'mvim', and 'vim' and returns the first one found
    that is compiled with the +clientserver feature. Skips tests if not found.
    """
    for executable in ['gvim', 'mvim', 'vim']:
        path = shutil.which(executable)
        if not path:
            continue
        try:
            output = subprocess.check_output(
                [path, '--version'], text=True, stderr=subprocess.STDOUT
            )
            if '+clientserver' in output:
                return path
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    pytest.skip("Vim with +clientserver support not available")

import os
import pytest

def test_no_inquirerpy_stub_directory():
    """
    Ensures that the InquirerPy stub directory does not exist in the project root.
    This prevents issues where a local stub might shadow the installed InquirerPy package.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    inquirerpy_stub_path = os.path.join(project_root, 'InquirerPy')
    assert not os.path.isdir(inquirerpy_stub_path), (
        f"Found unexpected InquirerPy stub directory at {inquirerpy_stub_path}. "
        "Please remove it and ensure InquirerPy is installed via requirements.txt."
    )

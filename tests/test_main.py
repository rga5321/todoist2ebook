
import pytest
from unittest.mock import patch, MagicMock
import os
import sys

# Add parent directory to path to import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import parse_env_list, main

def test_parse_env_list():
    assert parse_env_list("['a', 'b']") == ['a', 'b']
    assert parse_env_list("[]") == []
    assert parse_env_list("invalid") == []

@patch('subprocess.check_output')
@patch('subprocess.run')
@patch('main.add_qr_to_epub')
@patch('main.send_email')
def test_main_execution(mock_send_email, mock_add_qr, mock_run, mock_check_output):
    # Setup mocks
    mock_check_output.side_effect = [
        b"2025-01-01_1200\n", # date
        b"Calibre 5.0" # version
    ]
    
    # Mock environment variables
    with patch.dict(os.environ, {
        "SEND_EMAIL": "True",
        "DESTINATION_EMAIL": "test@example.com",
        "SMTP_SERVER": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "user",
        "SMTP_PASSWORD": "password",
        "SMTP_FROM": "sender@example.com"
    }):
        main()
        
    # Verify calls
    assert mock_run.called
    assert mock_add_qr.called
    assert mock_send_email.called

@patch('subprocess.check_output')
@patch('subprocess.run')
@patch('main.add_qr_to_epub')
@patch('main.send_email')
def test_main_no_email(mock_send_email, mock_add_qr, mock_run, mock_check_output):
    # Setup mocks
    mock_check_output.side_effect = [
        b"2025-01-01_1200\n", # date
        b"Calibre 5.0" # version
    ]
    
    # Mock environment variables
    with patch.dict(os.environ, {
        "SEND_EMAIL": "False"
    }):
        main()
        
    # Verify email was NOT sent
    assert not mock_send_email.called

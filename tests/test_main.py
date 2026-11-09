
import pytest
from unittest.mock import patch, MagicMock
import os
import subprocess
import sys

# Add parent directory to path to import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import main, run_ebook_convert


@patch('main.run_ebook_convert')
@patch('subprocess.check_output')
@patch('subprocess.run')
@patch('main.add_qr_to_epub')
@patch('main.remove_empty_sections')
@patch('main.send_email')
def test_main_execution(mock_send_email, mock_remove_empty, mock_add_qr, mock_run, mock_check_output, mock_run_ebook):
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
    assert mock_run_ebook.called
    assert mock_run.called
    assert mock_remove_empty.called
    assert mock_add_qr.called
    assert mock_send_email.called

@patch('main.run_ebook_convert')
@patch('subprocess.check_output')
@patch('subprocess.run')
@patch('main.add_qr_to_epub')
@patch('main.remove_empty_sections')
@patch('main.send_email')
def test_main_no_email(mock_send_email, mock_remove_empty, mock_add_qr, mock_run, mock_check_output, mock_run_ebook):
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


@patch('main.run_ebook_convert')
@patch('subprocess.check_output')
@patch('subprocess.run')
@patch('main.add_qr_to_epub')
@patch('main.remove_empty_sections')
@patch('main.send_email')
def test_main_continues_when_section_cleanup_fails(
    mock_send_email,
    mock_remove_empty,
    mock_add_qr,
    mock_run,
    mock_check_output,
    mock_run_ebook,
):
    mock_check_output.side_effect = [
        b"2025-01-01_1200\n",  # date
        b"Calibre 5.0",  # version
    ]
    mock_remove_empty.side_effect = RuntimeError("cleanup failed")

    with patch.dict(os.environ, {"SEND_EMAIL": "False"}):
        main()

    assert mock_remove_empty.called
    assert mock_add_qr.called


def test_run_ebook_convert_filters_recipe_specific_option(capsys):
    script = (
        "print('Conversion options changed from defaults:')\n"
        "print('  recipe_specific_option: [\"TODOIST_API_KEY:SECRET\"]')\n"
        "print('normal output')"
    )

    run_ebook_convert([sys.executable, "-c", script], os.environ.copy())

    captured = capsys.readouterr()
    assert "SECRET" not in captured.out
    assert "recipe_specific_option" not in captured.out
    assert "normal output" in captured.out


def test_run_ebook_convert_filters_api_key_line(capsys):
    script = (
        "print('Recipe specific options:')\n"
        "print('  ARCHIVE_DOWNLOADED = False')\n"
        "print('  TODOIST_API_KEY = SECRET')\n"
        "print('normal output')"
    )

    run_ebook_convert([sys.executable, "-c", script], os.environ.copy())

    captured = capsys.readouterr()
    assert "SECRET" not in captured.out
    assert "TODOIST_API_KEY" not in captured.out
    assert "ARCHIVE_DOWNLOADED = False" in captured.out
    assert "normal output" in captured.out


def test_run_ebook_convert_raises_on_failure():
    with pytest.raises(subprocess.CalledProcessError):
        run_ebook_convert(
            [sys.executable, "-c", "import sys; sys.exit(3)"],
            os.environ.copy(),
        )

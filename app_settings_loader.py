"""
USAGE:

from app_settings_loader import ensure_settings_ini, get_setting

# Ensure settings.ini exists and is up to date
ensure_settings_ini()

# Get settings as needed
host = get_setting('FLASK', 'FLASK_HOST', fallback='0.0.0.0')
port = get_setting('FLASK', 'FLASK_PORT', fallback=5000, type_=int)
debug = get_setting('FLASK', 'DEBUG', fallback=False, type_=bool)
notes_dir = get_setting('FLASK', 'NOTES_DIR', fallback='notes')

# You can also use the preloaded variables if you want:
# FLASK_HOST, FLASK_PORT, SECRET_KEY, DEBUG, NOTES_DIR, MAX_CONTENT_LENGTH
"""

import configparser
from pathlib import Path

DEFAULT_CONFIG = {
    'FLASK': {
        'FLASK_HOST': '0.0.0.0',
        'FLASK_PORT': '5000',
        'SECRET_KEY': 'change-this-secret',
        'DEBUG': 'False',
        'Specify location where your notes .md files are at - the root folder': None,
        'NOTES_DIR': 'notes',
        'Maximum content length in MB': None,
        'MAX_CONTENT_LENGTH': '16',
    },
}

CONFIG_FILE = 'settings.ini'

def ensure_settings_ini():
    """
    Ensure that settings.ini exists and contains all required settings.
    - If the file does not exist, it is created with default values and comments.
    - If the file exists but is missing any required setting, only the missing setting(s) 
      are added with default values (existing values and comments are not changed).
    """
    # First check if file exists at all
    if not Path(CONFIG_FILE).exists():
        # Create new file with all default settings and comments
        with open(CONFIG_FILE, 'w') as f:
            for section, values in DEFAULT_CONFIG.items():
                f.write(f'[{section}]\n')
                
                # Get all items in order
                items = list(values.items())
                
                # Process each item in order
                for i, (key, value) in enumerate(items):
                    if value is not None:  # This is a setting
                        # Find the comment that belongs right before this setting
                        prev_comment = None
                        # Look backwards from current position to find the nearest comment
                        for prev_key, prev_val in reversed(items[:i]):
                            if prev_val is None:  # It's a comment
                                # Check no other setting exists between comment and current setting
                                has_setting_between = any(
                                    k for k, v in items[:i]
                                    if v is not None and 
                                    prev_key.upper() < k.upper() < key.upper()
                                )
                                if not has_setting_between:
                                    prev_comment = prev_key
                                    break
                        
                        # Write the comment if found
                        if prev_comment:
                            f.write(f'; {prev_comment}\n')
                        # Write the setting
                        f.write(f'{key} = {value}\n')
                f.write('\n')
        return

    # If file exists, read it line by line to preserve comments and case
    with open(CONFIG_FILE, 'r') as f:
        lines = f.readlines()
    
    # Parse existing settings while preserving case
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    
    # Track what settings we've seen and what we need to add
    current_section = None
    settings_seen = {section: set() for section in DEFAULT_CONFIG}
    missing_settings = {}
    changed = False
    
    # First pass: identify missing settings while preserving case
    for section in DEFAULT_CONFIG:
        missing_settings[section] = {}
        if section not in config:
            # New section needed
            changed = True
            continue
            
        for key, value in DEFAULT_CONFIG[section].items():
            if value is not None:  # Skip comments
                key_lower = key.lower()
                # Check if setting exists (case-insensitive)
                if not any(k.lower() == key_lower for k in config[section]):
                    missing_settings[section][key] = value
                    changed = True
                else:
                    # Remember the actual case of existing keys
                    for existing_key in config[section]:
                        if existing_key.lower() == key_lower:
                            settings_seen[section].add(existing_key)
    
    if not changed:
        return
        
    # Second pass: write the updated file
    new_lines = []
    current_section = None
    
    for line in lines:
        line = line.rstrip('\n')
        
        # Handle section headers
        if line.strip().startswith('[') and line.strip().endswith(']'):
            if current_section and current_section in missing_settings and missing_settings[current_section]:
                # Remove trailing empty lines before adding missing settings
                while new_lines and not new_lines[-1].strip():
                    new_lines.pop()
                # Add any missing settings before moving to next section
                for key, value in missing_settings[current_section].items():
                    new_lines.append(f'{key} = {value}')
                new_lines.append('')  # Single newline after section
            
            current_section = line.strip('[]').strip()
            new_lines.append(line)
            
            # If this is a new section, add all its settings
            if current_section in DEFAULT_CONFIG and current_section not in config:
                for key, value in DEFAULT_CONFIG[current_section].items():
                    if value is not None:  # Only add settings, not comments
                        new_lines.append(f'{key} = {value}')
                new_lines.append('')  # Single newline after section
            continue
            
        # Skip empty lines at the end of sections
        if line.strip() or not current_section:
            new_lines.append(line)
    
    # Handle missing settings in the last section
    if current_section and current_section in missing_settings and missing_settings[current_section]:
        # Remove trailing empty lines before adding missing settings
        while new_lines and not new_lines[-1].strip():
            new_lines.pop()
        # Add missing settings
        for key, value in missing_settings[current_section].items():
            new_lines.append(f'{key} = {value}')
        new_lines.append('')  # Single newline after section
    
    # Write the updated file
    with open(CONFIG_FILE, 'w') as f:
        f.write('\n'.join(new_lines) + '\n')

def get_setting(section, key, fallback=None, type_=str):
    """
    Retrieve a setting from settings.ini.
    Args:
        section (str): The section in the ini file (e.g. 'FLASK').
        key (str): The key to retrieve.
        fallback: The value to return if the key is not found.
        type_ (type): Optionally convert the value to int or bool. Default is str.
    Returns:
        The value from settings.ini, converted to the requested type if specified.
    """
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    if config.has_option(section, key):
        value = config.get(section, key)
        if type_ == int:
            try:
                return int(value)
            except Exception:
                return fallback if fallback is not None else 0
        if type_ == bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        return value
    return fallback

# Load settings from the configuration file settings.ini
FLASK_HOST = get_setting('FLASK', 'FLASK_HOST', fallback='0.0.0.0')
FLASK_PORT = get_setting('FLASK', 'FLASK_PORT', fallback=5000, type_=int)
SECRET_KEY = get_setting('FLASK', 'SECRET_KEY', fallback='change-this')
DEBUG = get_setting('FLASK', 'DEBUG', fallback='INFO')
NOTES_DIR = Path(get_setting('FLASK', 'NOTES_DIR', fallback='notes')).resolve()
MAX_CONTENT_LENGTH = get_setting('FLASK', 'MAX_CONTENT_LENGTH', fallback=16, type_=int)

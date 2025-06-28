from flask import url_for, jsonify, current_app
import os
import mistune
from pathlib import Path
import re
from app_settings_loader import ROOT_DIR, get_setting
from datetime import datetime
import magic  # For file type detection


def resolve_path(path: str, base_dir: str) -> str:
    """
    Resolves the given path:
    - If it's an absolute path, returns it as-is.
    - If it's a relative path or just a folder name, returns the path joined with base_dir.
    """
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(base_dir, path))

def as_path(path: str | Path) -> Path:
    return path if isinstance(path, Path) else Path(path)

NOTES_FOLDER = get_setting('MD_NOTES_APP', 'NOTES_DIR', fallback='notes')
NOTES_FOLDER = resolve_path(NOTES_FOLDER, ROOT_DIR)
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

# Custom markdown renderer to handle Obsidian image syntax
class ObsidianRenderer(mistune.HTMLRenderer):
    def image(self, src, alt="", title=None):
        # Handle Obsidian-style ![[...]] or relative paths from any storage location
        # Strip any ![[...]] wrapper
        stripped_src = re.sub(r'^!\[\[(.*)\]\]$', r'\1', src)
        image_match = re.match(r'(?:.*/)?([\w\- .]+\.(?:png|jpg|jpeg|gif|webp))', stripped_src, re.IGNORECASE)
        if image_match:
            # Get storage info based on current note path
            note_path = getattr(current_app, 'current_note_path', None)
            storage_dir, storage_base = get_image_storage_info(note_path)
            storage_mode = get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_MODE')
            
            # Clean up the path and normalize slashes
            clean_path = os.path.normpath(stripped_src).replace('\\', '/').strip('/')
            
            # Use appropriate endpoint based on storage mode
            if storage_mode == '2':
                # Mode 2: Specific storage folder - just the filename
                image_url = url_for('md_viewer.serve_stored_image', filename=os.path.basename(clean_path))
            else:
                # For modes 1, 3, and 4 - use path as provided in markdown
                # The paths in markdown should already be correct based on the mode:
                # Mode 1: just filename.png
                # Mode 3: filename.png (same directory as note)
                # Mode 4: subfolder/filename.png
                image_url = url_for('md_viewer.serve_attatched_image', image_path=clean_path)
            
            return f'<img src="{image_url}" alt="{alt}" title="{title or alt}">'
        return super().image(src, alt, title)


# Helper functions
def get_image_storage_info(note_path=None):
    """
    Determine the image storage directory and relative path based on the selected mode and note path.
    Mode 1: Store directly in NOTES_DIR
    Mode 2: Store in specific folder (IMAGE_STORAGE_PATH)
    Mode 3: Store in same directory as the note
    Mode 4: Store in subfolder (IMAGE_SUBFOLDER_NAME) in the note's directory
    
    Args:
        note_path: Path to the .md file, relative to NOTES_DIR
    
    Returns: (storage_dir, markdown_path) where
        storage_dir is the absolute Path where the image will be stored
        markdown_path is the path to use in the markdown link (None means use actual location)
        
    Raises:
        ValueError: If the requested location is in a skipped directory
    """
    # Check if the path is in a skipped directory
    if note_path:
        skip_dirs = get_setting('MD_NOTES_APP', 'NOTES_DIR_SKIP', '').strip().split(',')
        skip_dirs = [d.strip() for d in skip_dirs if d.strip()]
        
        # Check if any part of the path is in skip_dirs
        path_parts = Path(note_path).parts
        for part in path_parts:
            if part in skip_dirs:
                raise ValueError(f"Cannot access content in skipped directory: {part}")
    mode = get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_MODE')
    notes_dir = Path(NOTES_FOLDER).resolve()
    
    if mode == '1':  # Store directly in NOTES_DIR
        return notes_dir, None
        
    elif mode == '2':  # Store in specific folder
        storage_dir = Path(get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_PATH')).resolve()
        # Will use special url_for for mode 2, so no markdown path needed
        return storage_dir, None
        
    elif mode in ['3', '4'] and note_path:  # Store relative to note
        # Ensure we're using the directory of the actual .md file
        if note_path.endswith('.md'):
            note_dir = notes_dir / os.path.dirname(note_path)
        else:
            # If it's not a .md file, assume it's a directory and use that
            note_dir = notes_dir / note_path
            
        if mode == '3':
            # No special path needed, image will be in same dir as note
            return note_dir, None
        else:  # mode == '4'
            subfolder_name = get_setting('MD_NOTES_APP', 'IMAGE_SUBFOLDER_NAME')
            storage_dir = note_dir / subfolder_name
            # Return just subfolder name for markdown
            return storage_dir, subfolder_name
        
    # Default to mode 1 if invalid mode or missing note_path
    return notes_dir, None

def build_tree_structure(directory, base_path=None, level=0):
    """Build a tree structure from the directory, excluding hidden folders and those in NOTES_DIR_SKIP/HIDE_SIDEPANE."""
    if base_path is None:
        base_path = directory

    # Get folders to skip or hide from settings
    skip_dirs = get_setting('MD_NOTES_APP', 'NOTES_DIR_SKIP', '').strip().split(',')
    skip_dirs = [d.strip() for d in skip_dirs if d.strip()]
    
    hide_dirs = get_setting('MD_NOTES_APP', 'NOTES_DIR_HIDE_SIDEPANE', '').strip().split(',')
    hide_dirs = [d.strip() for d in hide_dirs if d.strip()]
    
    # Add the attatched folder name to hidden list
    subfolder_name = get_setting('MD_NOTES_APP', 'IMAGE_SUBFOLDER_NAME', fallback='attatched')
    if subfolder_name and subfolder_name not in hide_dirs:
        hide_dirs.append(subfolder_name)

    tree = []
    try:
        for item in sorted(as_path(directory).iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            # Skip hidden files, completely skip directories, and side panel hidden directories
            if (item.name.startswith('.') or 
                (item.is_dir() and item.name in skip_dirs) or 
                (item.is_dir() and item.name in hide_dirs)):
                continue
                
            rel_path = str(item.relative_to(base_path))
            node = {
                'name': item.name,
                'type': 'dir' if item.is_dir() else 'file',
                'path': rel_path,
                'level': level,
                'expanded': False  # Default to collapsed
            }
            
            if item.is_dir():
                node['children'] = build_tree_structure(item, base_path, level + 1)
            elif item.suffix == '.md':  # Only include .md files
                node['display_name'] = item.stem  # Just use filename without extension
            else:
                continue  # Skip non-markdown files
                
            tree.append(node)
    except Exception as e:
        print(f"Error reading directory {directory}: {str(e)}")
        
    return tree

def get_path_components(path):
    """Convert a file path into a list of directory names."""
    if not path:
        return []
    parts = path.split('/')
    return ['/'.join(parts[:i+1]) for i in range(len(parts)-1)]

def generate_breadcrumbs(note_path, title=None):
    """Generate breadcrumb data for a given note path."""
    crumbs = []
    parts = note_path.split('/')
    current_path = ''
    
    # Add root
    crumbs.append({'name': '/', 'url': url_for('md_viewer.index')})
    
    # Add directories
    for i, part in enumerate(parts[:-1]):  # Skip the file name
        current_path = current_path + '/' + part if current_path else part
        crumbs.append({
            'name': part,
            'url': url_for('md_viewer.folder', folder_path=current_path)
        })
    
    # Add the file name (always use file name without .md)
    if len(parts) > 0:
        name = parts[-1][:-3] if parts[-1].endswith('.md') else parts[-1]
        url = None if parts[-1].endswith('.md') else url_for('md_viewer.folder', folder_path=current_path + '/' + parts[-1] if current_path else parts[-1])
        crumbs.append({'name': name, 'url': url})
        
    return crumbs

# Update app config from settings.ini
def update_app_config():
    """Update app config from settings.ini"""
    try:
        current_app.config['NOTES_DIR'] = Path(get_setting('MD_NOTES_APP', 'NOTES_DIR')).resolve()
        current_app.config['IMAGE_STORAGE_MODE'] = get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_MODE')
        current_app.config['IMAGE_STORAGE_PATH'] = get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_PATH')
        current_app.config['IMAGE_SUBFOLDER_NAME'] = get_setting('MD_NOTES_APP', 'IMAGE_SUBFOLDER_NAME')
    except Exception as e:
        current_app.logger.error(f"Error updating app config: {str(e)}")

def get_all_folders(directory, base_path=None, level=0):
    """Get a flat list of all folders in the directory with their paths and levels."""
    if base_path is None:
        base_path = directory
    
    folders = []
    try:
        for item in sorted(as_path(directory).iterdir(), key=lambda x: x.name.lower()):
            if item.name.startswith('.') or (item.is_dir() and item.name == 'attatched'):
                continue
            
            if item.is_dir():
                rel_path = str(item.relative_to(base_path))
                folders.append({
                    'name': item.name,
                    'path': rel_path,
                    'level': level
                })
                # Recursively get subfolders
                folders.extend(get_all_folders(item, base_path, level + 1))
    except Exception as e:
        print(f"Error reading directory {directory}: {str(e)}")
    
    return folders

def check_notes_dir_security(path):
    """
    Check if a path is secure to use as notes directory.
    Returns (is_valid, error_message)
    """
    try:
        # Convert to absolute path
        abs_path = Path(path).resolve()
        
        # Check for system directories we want to protect
        system_dirs = [
            '/bin', '/boot', '/dev', '/etc', '/lib', '/lib64', '/proc', 
            '/root', '/run', '/sbin', '/sys', '/tmp', '/usr', '/var',
            '/opt', '/lost+found'
        ]
        
        str_path = str(abs_path)
        for sys_dir in system_dirs:
            if str_path == sys_dir or str_path.startswith(sys_dir + '/'):
                return False, f'Cannot use system directory: {sys_dir}'

        # Check if path contains forbidden characters
        if any(char in str_path for char in ['\\', '*', '?', '"', '<', '>', '|', ';', '&']):
            return False, 'Path contains invalid characters'

        # Don't allow paths that are too short
        if len(str_path) < 2:
            return False, 'Path is too short'

        return True, None

    except Exception as e:
        return False, f'Invalid path: {str(e)}'
    
def handle_uploaded_image(request_files, note_path=None):
    """Handle an image upload from the markdown editor."""
    if 'image' not in request_files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request_files['image']
    if file.filename == '':
        return jsonify({'error': 'No image file selected'}), 400
    
    if not allowed_image_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    # Get storage directory based on mode and note path
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'Pasted_image_{timestamp}{Path(file.filename).suffix}'
    storage_dir, storage_subfolder = get_image_storage_info(note_path)
    storage_mode = get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_MODE')

    try:
        # Create storage directory if needed
        os.makedirs(storage_dir, exist_ok=True)
        filepath = storage_dir / filename
        file.save(filepath)

        # Construct the markdown link and relative path based on storage mode
        if storage_mode == '1':
            # Mode 1: Direct in NOTES_DIR root - just the filename
            markdown = f'![[{filename}]]'
            relative_path = filename
        elif storage_mode == '2':
            # Mode 2: Specific storage folder - use special URL
            return jsonify({
                'filename': filename,
                'url': url_for('md_viewer.serve_stored_image', filename=filename),
                'markdown': f'![[{filename}]]'
            })
        elif storage_mode == '3':
            # Mode 3: Same directory as note - just the filename since it's in same dir
            markdown = f'![[{filename}]]'
            # For serving, we need the full relative path from NOTES_DIR
            note_dir = os.path.dirname(note_path) if note_path else ''
            relative_path = f'{note_dir}/{filename}' if note_dir else filename
        elif storage_mode == '4':
            # Mode 4: In subfolder under note - include the configured subfolder name
            if storage_subfolder:  # Should always be true for mode 4
                markdown = f'![[{storage_subfolder}/{filename}]]'
                # For serving, we need the full relative path from NOTES_DIR
                note_dir = os.path.dirname(note_path) if note_path else ''
                relative_path = f'{note_dir}/{storage_subfolder}/{filename}' if note_dir else f'{storage_subfolder}/{filename}'
            else:
                # Fallback if somehow storage_subfolder is None
                markdown = f'![[{filename}]]'
                relative_path = filename
        else:
            # Default to mode 1 behavior
            markdown = f'![[{filename}]]'
            relative_path = filename

        # Clean up any double slashes in paths
        relative_path = re.sub(r'/+', '/', relative_path)

        # Return the appropriate URL for serving the image
        return jsonify({
            'filename': filename,
            'url': url_for('md_viewer.serve_attatched_image', image_path=relative_path),
            'markdown': markdown
        })

    except Exception as e:
        return jsonify({'error': f'Failed to save image: {str(e)}'}), 500
    

def get_allowed_file_types():
    """Get allowed file types from settings"""
    # Get configurable extensions
    image_extensions = set('.' + ext.strip() for ext in get_setting('MD_NOTES_APP', 'ALLOWED_IMAGE_EXTENSIONS', 
                                                                  fallback='jpg,jpeg,png,bmp').split(','))
    file_extensions = set('.' + ext.strip() for ext in get_setting('MD_NOTES_APP', 'ALLOWED_FILE_EXTENSIONS',
                                                                 fallback='txt,csv,json,html,htm,xml,yaml,yml,js,css,py,md').split(','))

    # Build file types dictionary
    return {
        'images': image_extensions,
        'text': file_extensions
    }

def get_file_type(extension):
    """Determine file type based on extension"""
    if not extension:
        return None
        
    allowed_types = get_allowed_file_types()
    extension = extension.lower()
    
    for type_name, extensions in allowed_types.items():
        if extension in extensions:
            return type_name
    
    return None

def get_language_from_extension(extension):
    """Map file extensions to highlight.js language classes"""
    extension = extension.lower()
    language_map = {
        '.html': 'html',
        '.htm': 'html',
        '.js': 'javascript',
        '.css': 'css',
        '.json': 'json',
        '.py': 'python',
        '.xml': 'xml',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.ini': 'ini',
        '.txt': 'plaintext',
        '.log': 'plaintext',
        '.csv': 'plaintext'
    }
    return language_map.get(extension, 'plaintext')

def verify_file_type(file_path, claimed_extension):
    """
    Verify that the file's content matches its claimed extension.
    Returns tuple (is_valid, actual_type)
    """
    mime = magic.Magic(mime=True)
    file_type = mime.from_file(str(file_path))
    
    # Define allowed MIME types for each extension
    extension_mime_types = {
        # Images
        '.jpg': ['image/jpeg'],
        '.jpeg': ['image/jpeg'],
        '.png': ['image/png'],
        '.gif': ['image/gif'],
        '.bmp': ['image/bmp'],
        '.webp': ['image/webp'],
        # Documents
        '.pdf': ['application/pdf'],
        '.txt': ['text/plain'],
        '.md': ['text/plain', 'text/markdown'],
        '.csv': ['text/csv', 'text/plain'],
        '.json': ['application/json', 'text/plain'],
        '.xml': ['application/xml', 'text/xml', 'text/plain'],
        '.yaml': ['text/plain', 'text/yaml'],
        '.yml': ['text/plain', 'text/yaml'],
        '.ini': ['text/plain'],
        '.log': ['text/plain'],
        # Code files
        '.js': ['text/javascript', 'application/javascript', 'text/plain'],
        '.css': ['text/css', 'text/plain'],
        '.py': ['text/x-python', 'text/plain'],
        '.html': ['text/html', 'text/plain'],
        '.htm': ['text/html', 'text/plain']
    }
    
    # Get allowed MIME types for the claimed extension
    allowed_mime_types = extension_mime_types.get(claimed_extension.lower(), [])
    
    # Special case for text files - if it's claimed to be a text format
    # and the MIME type indicates it's text, consider it valid
    text_extensions = {'.txt', '.md', '.csv', '.json', '.xml', '.yaml', '.yml', 
                      '.ini', '.log', '.js', '.css', '.py', '.html', '.htm'}
    if claimed_extension.lower() in text_extensions and (
        file_type.startswith('text/') or 
        'charset=us-ascii' in file_type or 
        'charset=utf-8' in file_type
    ):
        return True, file_type
    
    return file_type in allowed_mime_types, file_type
# app.py
from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
from werkzeug.exceptions import HTTPException
import os
import mistune
from pathlib import Path
import re
from app_settings_loader import ensure_settings_ini, FLASK_HOST, FLASK_PORT, SECRET_KEY, DEBUG, NOTES_DIR, MAX_CONTENT_LENGTH

app = Flask(__name__)
ensure_settings_ini()

app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = DEBUG
app.config['NOTES_DIR'] = NOTES_DIR
max_content_length = MAX_CONTENT_LENGTH * 1024 * 1024  # Convert MB to bytes
app.config['MAX_CONTENT_LENGTH'] = max_content_length

# Custom error handler using base.html
@app.errorhandler(Exception)
def handle_error(error):
    if isinstance(error, HTTPException):
        code = error.code
        message = getattr(error, 'description', str(error))
    else:
        code = 500
        message = str(error)
    return render_template('error.html', message=message, error=error), code

# Create directory for notes if it doesn't exist
if not app.config['NOTES_DIR'].exists():
    os.makedirs(app.config['NOTES_DIR'])

def build_tree_structure(directory, base_path=None, level=0):
    """Build a tree structure from the directory."""
    if base_path is None:
        base_path = directory

    tree = []
    try:
        for item in sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if item.name.startswith('.'):  # Skip hidden files
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
    crumbs.append({'name': '/', 'url': url_for('index')})
    
    # Add directories
    for i, part in enumerate(parts[:-1]):  # Skip the file name
        current_path = current_path + '/' + part if current_path else part
        crumbs.append({
            'name': part,
            'url': url_for('folder', folder_path=current_path)
        })
    
    # Add the file name (always use file name without .md)
    if len(parts) > 0:
        name = parts[-1][:-3] if parts[-1].endswith('.md') else parts[-1]
        url = None if parts[-1].endswith('.md') else url_for('folder', folder_path=current_path + '/' + parts[-1] if current_path else parts[-1])
        crumbs.append({'name': name, 'url': url})
        
    return crumbs

@app.route('/')
def index():
    folder_contents = []
    try:
        for item in sorted(app.config['NOTES_DIR'].iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if item.name.startswith('.'):  # Skip hidden files
                continue
            
            is_dir = item.is_dir()
            rel_path = str(item.relative_to(app.config['NOTES_DIR']))
            
            if is_dir or item.suffix == '.md':  # Only include directories and markdown files
                folder_contents.append({
                    'name': item.name,
                    'type': 'dir' if is_dir else 'file',
                    'path': rel_path,
                    'display_name': item.name if is_dir else item.stem  # Show full name for folders, remove .md for files
                })
    except Exception as e:
        print(f"Error reading root directory: {str(e)}")

    notes_tree = build_tree_structure(app.config['NOTES_DIR'])
    return render_template('folder.html', 
                         folder_path='',
                         folder_contents=folder_contents,
                         notes_tree=notes_tree, 
                         active_path=[], 
                         current_note=None,
                         breadcrumbs=generate_breadcrumbs(''))

@app.route('/note/<path:note_path>')
def note(note_path):
    full_path = Path(app.config['NOTES_DIR']) / note_path
    if not full_path.is_file() or not note_path.endswith('.md'):
        return "Note not found", 404

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Convert markdown to HTML
        renderer = mistune.HTMLRenderer()
        markdown_parser = mistune.Markdown(renderer=renderer)
        html_content = markdown_parser(content)

        # Build tree and get path components
        notes_tree = build_tree_structure(app.config['NOTES_DIR'])
        active_path = get_path_components(note_path)
        # Use file name (without .md) for breadcrumbs and title
        title = full_path.stem
        breadcrumbs = generate_breadcrumbs(note_path, title)

        return render_template('note.html', 
                            content=content,
                            html_content=html_content,
                            title=title,
                            notes_tree=notes_tree,
                            active_path=active_path,
                            current_note=note_path,
                            breadcrumbs=breadcrumbs)
    except Exception as e:
        return f"Error reading note: {str(e)}", 500

@app.route('/edit/<path:note_path>', methods=['GET', 'POST'])
def edit_note(note_path):
    full_path = Path(app.config['NOTES_DIR']) / note_path
    if not full_path.is_file() or not note_path.endswith('.md'):
        return "Note not found", 404

    if request.method == 'POST':
        new_content = request.form.get('content', '')
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return redirect(url_for('note', note_path=note_path))
        except Exception as e:
            return f"Error saving note: {str(e)}", 500

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
            title = full_path.stem
        notes_tree = build_tree_structure(app.config['NOTES_DIR'])
        active_path = get_path_components(note_path)
        breadcrumbs = generate_breadcrumbs(note_path, f"Edit {title}")

        return render_template('edit.html',
                            content=content,
                            title=title,
                            notes_tree=notes_tree,
                            active_path=active_path,
                            current_note=note_path,
                            breadcrumbs=breadcrumbs)
    except Exception as e:
        return f"Error reading note: {str(e)}", 500

def get_all_folders(directory, base_path=None, level=0):
    """Get a flat list of all folders in the directory with their paths and levels."""
    if base_path is None:
        base_path = directory
    
    folders = []
    try:
        for item in sorted(directory.iterdir(), key=lambda x: x.name.lower()):
            if item.name.startswith('.'):  # Skip hidden files
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

@app.route('/create', methods=['GET', 'POST'])
def create_note():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            abort(400, description="Note title is required")
        
        # Validate file name: only allow safe characters
        # Letters, numbers, dash, underscore, dot (no slashes)
        if not re.match(r'^[\w\-. ]+$', title):
            return "Invalid file name. Only letters, numbers, dash, underscore, dot, and space are allowed.", 400
        if '/' in title or '\\' in title:
            return "Invalid file name. Slashes are not allowed.", 400
        if title.startswith('.') or title.endswith('.'):
            return "Invalid file name. Cannot start or end with a dot.", 400
        if title in ['CON', 'PRN', 'AUX', 'NUL'] or re.match(r'^COM[1-9]$|^LPT[1-9]$', title, re.IGNORECASE):
            return "Invalid file name.", 400

        content = request.form.get('content', '').strip()
        path = request.form.get('path', '').strip()

        # Use the title as the file name
        filename = f"{title}.md"
        
        try:
            # Safely resolve the full path to ensure it's within NOTES_DIR
            if path:
                dir_path = (Path(app.config['NOTES_DIR']) / path).resolve()
                if not str(dir_path).startswith(str(app.config['NOTES_DIR'].resolve())):
                    return "Invalid folder path", 400
                os.makedirs(dir_path, exist_ok=True)
                file_path = dir_path / filename
            else:
                file_path = Path(app.config['NOTES_DIR']) / filename

            # Final safety check
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(app.config['NOTES_DIR'].resolve())):
                return "Invalid file path", 400

            # Check if file already exists
            if file_path.exists():
                return "A note with this name already exists in the selected folder. Please choose a different name.", 400

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            # Use os.path.relpath for robust path calculation
            rel_path = os.path.relpath(str(file_path), str(app.config['NOTES_DIR']))
            return redirect(url_for('note', note_path=rel_path))
        except Exception as e:
            abort(500, description=f"Error creating note: {str(e)}")

    # Get all available folders for autocomplete
    available_folders = get_all_folders(app.config['NOTES_DIR'])
    
    # Get current folder from query parameter if provided
    current_folder = request.args.get('folder', '')
    
    notes_tree = build_tree_structure(app.config['NOTES_DIR'])
    return render_template('create.html', 
                         notes_tree=notes_tree,
                         available_folders=available_folders,
                         current_folder=current_folder,
                         active_path=current_folder.split('/') if current_folder else [],
                         current_note=None)

@app.route('/delete/<path:note_path>', methods=['POST'])
def delete_note(note_path):
    full_path = Path(app.config['NOTES_DIR']) / note_path
    if not full_path.is_file() or not note_path.endswith('.md'):
        return "Note not found", 404

    try:
        os.remove(full_path)
        return redirect(url_for('index'))
    except Exception as e:
        return f"Error deleting note: {str(e)}", 500

@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])

    results = []
    for root, _, files in os.walk(app.config['NOTES_DIR']):
        for file in files:
            if not file.endswith('.md'):
                continue

            try:
                file_path = Path(root) / file
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if query in content.lower():
                        title = file_path.stem  # Always use file name without .md
                        # Find context for the match
                        pos = content.lower().find(query)
                        start = max(0, pos - 50)
                        end = min(len(content), pos + len(query) + 50)
                        snippet = content[start:end].strip()

                        results.append({
                            'title': title,
                            'url': url_for('note', note_path=str(file_path.relative_to(app.config['NOTES_DIR']))),
                            'snippet': snippet
                        })
            except Exception as e:
                print(f"Error reading {file_path}: {str(e)}")

    return jsonify(results)

@app.route('/folder/<path:folder_path>')
def folder(folder_path):
    folder_full_path = Path(app.config['NOTES_DIR']) / folder_path
    if not folder_full_path.is_dir():
        return "Folder not found", 404

    notes_tree = build_tree_structure(app.config['NOTES_DIR'])
    
    # Get the current folder's contents
    current_folder = folder_full_path
    folder_contents = []
    try:
        for item in sorted(current_folder.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if item.name.startswith('.'):  # Skip hidden files
                continue
            
            is_dir = item.is_dir()
            rel_path = str(item.relative_to(app.config['NOTES_DIR']))
            
            if is_dir or item.suffix == '.md':  # Only include directories and markdown files
                folder_contents.append({
                    'name': item.name,
                    'type': 'dir' if is_dir else 'file',
                    'path': rel_path,
                    'display_name': item.name if is_dir else item.stem  # Show full name for folders, remove .md for files
                })
    except Exception as e:
        return f"Error reading folder: {str(e)}", 500

    return render_template('folder.html',
                         folder_path=folder_path,
                         folder_contents=folder_contents,
                         notes_tree=notes_tree,
                         active_path=folder_path.split('/'),
                         current_note=None,
                         breadcrumbs=generate_breadcrumbs(folder_path))


if __name__ == '__main__':
    app.run(debug=True, host=FLASK_HOST, port=FLASK_PORT)
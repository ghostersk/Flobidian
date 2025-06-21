# app.py
from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import mistune
from pathlib import Path
import uuid
import re
from urllib.parse import quote

def generate_slug(text):
    # Remove non-alphanumeric characters, replace spaces with hyphens, and lowercase
    slug = re.sub(r'[^a-zA-Z0-9\s]', '', text).strip().lower()
    slug = re.sub(r'\s+', '-', slug)
    return quote(slug)  # URL-encode for safety

app = Flask(__name__)
app.config['NOTES_DIR'] = Path('notes')  # Store Markdown files here
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

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
            'url': url_for('index') + '#' + current_path  # Using hash for directory navigation
        })
    
    # Add the file name (use title if provided)
    if len(parts) > 0:
        if title:
            crumbs.append({'name': title, 'url': None})
        else:
            crumbs.append({'name': parts[-1][:-3], 'url': None})  # Remove .md extension
            
    return crumbs

@app.route('/')
def index():
    notes_tree = build_tree_structure(app.config['NOTES_DIR'])
    return render_template('index.html', 
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
            title = full_path.stem
            if '##' in content:
                title = content.split('##')[1].split('\n')[0].strip()

        # Convert markdown to HTML
        renderer = mistune.HTMLRenderer()
        markdown_parser = mistune.Markdown(renderer=renderer)
        html_content = markdown_parser(content)

        # Build tree and get path components
        notes_tree = build_tree_structure(app.config['NOTES_DIR'])
        active_path = get_path_components(note_path)
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
            if '##' in content:
                title = content.split('##')[1].split('\n')[0].strip()

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

@app.route('/create', methods=['GET', 'POST'])
def create_note():
    if request.method == 'POST':
        title = request.form.get('title', '').strip() or 'Untitled Note'
        content = request.form.get('content', '').strip()
        path = request.form.get('path', '').strip()

        # Generate filename
        filename = f"{generate_slug(title)}.md"
        if path:
            # Create directories if they don't exist
            dir_path = Path(app.config['NOTES_DIR']) / path
            os.makedirs(dir_path, exist_ok=True)
            file_path = dir_path / filename
        else:
            file_path = Path(app.config['NOTES_DIR']) / filename

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"## {title}\n\n{content}")
            return redirect(url_for('note', note_path=str(file_path.relative_to(app.config['NOTES_DIR']))))
        except Exception as e:
            return f"Error creating note: {str(e)}", 500

    notes_tree = build_tree_structure(app.config['NOTES_DIR'])
    return render_template('create.html', notes_tree=notes_tree, active_path=[], current_note=None)

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
                        title = file_path.stem
                        if '##' in content:
                            title = content.split('##')[1].split('\n')[0].strip()

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

if __name__ == '__main__':
    app.run(debug=True)
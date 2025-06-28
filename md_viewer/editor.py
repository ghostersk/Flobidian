from flask import ( 
    render_template, request, redirect, url_for, jsonify, abort, 
    send_from_directory, current_app
    )
import os
from pathlib import Path
import re
from md_viewer.support_functions import (
    build_tree_structure, get_path_components, generate_breadcrumbs, 
    get_all_folders, get_image_storage_info, handle_uploaded_image,
    as_path, NOTES_FOLDER
)
from md_viewer import md_viewer_bp


@md_viewer_bp.route('/edit/<path:note_path>', methods=['GET', 'POST'])
def edit_note(note_path):
    full_path = Path(NOTES_FOLDER) / note_path
    if not full_path.is_file() or not note_path.endswith('.md'):
        return "Note not found", 404

    if request.method == 'POST':
        new_content = request.form.get('content', '')
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # Check if it's an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Note saved successfully'})
            else:
                return redirect(url_for('md_viewer.note', note_path=note_path))
        except Exception as e:
            error_msg = f"Error saving note: {str(e)}"
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg}), 500
            return error_msg, 500

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
            title = full_path.stem
        notes_tree = build_tree_structure(NOTES_FOLDER)
        active_path = get_path_components(note_path)
        breadcrumbs = generate_breadcrumbs(note_path, f"Edit {title}")
        note_dir = os.path.dirname(note_path)
        # Get storage info for this note
        storage_dir, storage_base = get_image_storage_info(note_path)
        
        return render_template('edit.html',
                            content=content,
                            title=title,
                            notes_tree=notes_tree,
                            active_path=active_path,
                            current_note=note_path,
                            note_dir=note_dir,
                            breadcrumbs=breadcrumbs,
                            storage_mode=current_app.config['IMAGE_STORAGE_MODE'],
                            storage_base=storage_base)
    except Exception as e:
        return f"Error reading note: {str(e)}", 500
    
@md_viewer_bp.route('/create', methods=['GET', 'POST'])
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
                dir_path = (as_path(NOTES_FOLDER) / path).resolve()
                if not str(dir_path).startswith(NOTES_FOLDER):
                    return "Invalid folder path", 400
                os.makedirs(dir_path, exist_ok=True)
                file_path = dir_path / filename
            else:
                file_path = as_path(NOTES_FOLDER) / filename

            # Final safety check
            file_path = file_path.resolve()
            if not str(file_path).startswith(NOTES_FOLDER):
                return "Invalid file path", 400

            # Check if file already exists
            if file_path.exists():
                return "A note with this name already exists in the selected folder. Please choose a different name.", 400

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            # Use os.path.relpath for robust path calculation
            rel_path = os.path.relpath(str(file_path), str(NOTES_FOLDER))
            return redirect(url_for('md_viewer.note', note_path=rel_path))
        except Exception as e:
            abort(500, description=f"Error creating note: {str(e)}")

    # Get all available folders for autocomplete
    available_folders = get_all_folders(NOTES_FOLDER)
    
    # Get current folder from query parameter if provided
    current_folder = request.args.get('folder', '')
    
    notes_tree = build_tree_structure(NOTES_FOLDER)
    return render_template('create.html', 
                         notes_tree=notes_tree,
                         available_folders=available_folders,
                         current_folder=current_folder,
                         active_path=current_folder.split('/') if current_folder else [],
                         current_note=None)

@md_viewer_bp.route('/delete/<path:note_path>', methods=['POST'])
def delete_note(note_path):
    full_path = Path(NOTES_FOLDER) / note_path
    if not full_path.is_file() or not note_path.endswith('.md'):
        return "Note not found", 404

    try:
        os.remove(full_path)
        return redirect(url_for('md_viewer.index'))
    except Exception as e:
        return f"Error deleting note: {str(e)}", 500
    
@md_viewer_bp.route('/upload_image/<path:note_path>', methods=['POST'])
def upload_image(note_path):
    return handle_uploaded_image(request.files, note_path)

@md_viewer_bp.route('/serve_image/<path:path>')
def serve_image(path):
    # Ensure the path is safe and within NOTES_DIR
    if '..' in path or path.startswith('/'):
        return 'Invalid image path', 400
    return send_from_directory(NOTES_FOLDER, path)
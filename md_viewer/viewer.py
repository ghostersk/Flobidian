from flask import render_template, request, url_for, jsonify, send_from_directory, current_app, Response
from werkzeug.utils import secure_filename
import os
import mistune
from pathlib import Path
from app_settings_loader import get_setting
from md_viewer.support_functions import (
    build_tree_structure, get_path_components, generate_breadcrumbs, 
    ObsidianRenderer, get_image_storage_info, as_path, NOTES_FOLDER,
    get_allowed_file_types, get_file_type, verify_file_type,
    )
from md_viewer import md_viewer_bp


NOTE_APP_NAME = get_setting('MD_NOTES_APP', 'NOTE_APP_NAME', fallback='Flask Blog')

@md_viewer_bp.context_processor
def inject_app_name():
    """Make app name available to all templates"""
    return {'app_name': NOTE_APP_NAME}

@md_viewer_bp.route('/')
def index():
    folder_contents = []
    try:
        # Get allowed extensions from settings
        allowed_image_extensions = get_setting('MD_NOTES_APP', 'ALLOWED_IMAGE_EXTENSIONS', '').split(',')
        allowed_file_extensions = get_setting('MD_NOTES_APP', 'ALLOWED_FILE_EXTENSIONS', '').split(',')
        
        # Clean the extensions (strip whitespace and ensure dot prefix)
        allowed_image_extensions = [f".{ext.strip()}" for ext in allowed_image_extensions if ext.strip()]
        allowed_file_extensions = [f".{ext.strip()}" for ext in allowed_file_extensions if ext.strip()]

        # Check if we should hide images
        images_hidden = get_setting('MD_NOTES_APP', 'IMAGES_FS_HIDE', fallback='False').lower() == 'true'

        for item in sorted(as_path(NOTES_FOLDER).iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if item.name.startswith('.'):  # Skip hidden files
                continue
            
            is_dir = item.is_dir()
            rel_path = str(item.relative_to(NOTES_FOLDER))
            
            if is_dir:
                folder_contents.append({
                    'name': item.name,
                    'type': 'dir',
                    'path': rel_path,
                    'display_name': item.name
                })
            else:
                # Get file type
                file_type = get_file_type(item.suffix)
                
                # Handle different file types
                if item.suffix == '.md':
                    # Always show markdown files
                    folder_contents.append({
                        'name': item.name,
                        'type': 'md',
                        'path': rel_path,
                        'display_name': item.stem
                    })
                elif file_type and (not images_hidden or file_type != 'images'):
                    # Show other supported files if not hidden
                    folder_contents.append({
                        'name': item.name,
                        'type': file_type,
                        'path': rel_path,
                        'display_name': item.name
                    })
    except Exception as e:
        print(f"Error reading root directory: {str(e)}")

    notes_tree = build_tree_structure(NOTES_FOLDER)
    return render_template('folder.html', 
                         folder_path='',
                         folder_contents=folder_contents,
                         notes_tree=notes_tree, 
                         active_path=[], 
                         current_note=None,
                         breadcrumbs=generate_breadcrumbs(''),
                         allowed_image_extensions=allowed_image_extensions,
                         allowed_file_extensions=allowed_file_extensions)

@md_viewer_bp.route('/note/<path:note_path>')
def note(note_path):
    full_path = Path(NOTES_FOLDER) / note_path
    if not full_path.is_file() or not note_path.endswith('.md'):
        return "Note not found", 404

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Store current note path for image processing
        current_app.current_note_path = note_path
        
        # Convert markdown to HTML using ObsidianRenderer
        renderer = ObsidianRenderer()
        markdown_parser = mistune.Markdown(renderer=renderer)
        html_content = markdown_parser(content)
        
        # Clear the note path after rendering
        current_app.current_note_path = None

        # Build tree and get path components
        notes_tree = build_tree_structure(NOTES_FOLDER)
        active_path = get_path_components(note_path)
        # Use file name (without .md) for breadcrumbs and title
        title = full_path.stem
        breadcrumbs = generate_breadcrumbs(note_path, title)

        # Get storage info for this note
        storage_dir, storage_base = get_image_storage_info(note_path)
        
        return render_template('note.html', 
                            content=content,
                            html_content=html_content,
                            title=title,
                            notes_tree=notes_tree,
                            active_path=active_path,
                            current_note=note_path,
                            breadcrumbs=breadcrumbs,
                            storage_mode=current_app.config['IMAGE_STORAGE_MODE'],
                            storage_base=storage_base)
    except Exception as e:
        return f"Error reading note: {str(e)}", 500
    
@md_viewer_bp.route('/search')
def search():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])

    results = []
    for root, _, files in os.walk(NOTES_FOLDER):
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
                            'url': url_for('md_viewer.note', note_path=str(file_path.relative_to(NOTES_FOLDER))),
                            'snippet': snippet
                        })
            except Exception as e:
                print(f"Error reading {file_path}: {str(e)}")

    return jsonify(results)

@md_viewer_bp.route('/folder/<path:folder_path>')
def folder(folder_path):
    folder_full_path = Path(NOTES_FOLDER) / folder_path
    if not folder_full_path.is_dir():
        return "Folder not found", 404

    notes_tree = build_tree_structure(NOTES_FOLDER)
    
    # Get allowed extensions from settings
    allowed_image_extensions = get_setting('MD_NOTES_APP', 'ALLOWED_IMAGE_EXTENSIONS', '').split(',')
    allowed_file_extensions = get_setting('MD_NOTES_APP', 'ALLOWED_FILE_EXTENSIONS', '').split(',')
    
    # Clean the extensions (strip whitespace and ensure dot prefix)
    allowed_image_extensions = [f".{ext.strip()}" for ext in allowed_image_extensions if ext.strip()]
    allowed_file_extensions = [f".{ext.strip()}" for ext in allowed_file_extensions if ext.strip()]
    
    # Get the current folder's contents
    current_folder = folder_full_path
    folder_contents = []
    try:
        # Check if we should hide images
        images_hidden = get_setting('MD_NOTES_APP', 'IMAGES_FS_HIDE', fallback='False').lower() == 'true'

        # Custom sort key function to order: folders first, then files (with images last)
        def sort_key(x):
            is_dir = x.is_dir()
            is_image = not is_dir and get_file_type(x.suffix) == 'images'
            return (not is_dir, is_image, x.name.lower())
            
        for item in sorted(current_folder.iterdir(), key=sort_key):
            if item.name.startswith('.'):  # Skip hidden files
                continue
            
            is_dir = item.is_dir()
            rel_path = str(item.relative_to(NOTES_FOLDER))
            
            if is_dir:
                folder_contents.append({
                    'name': item.name,
                    'type': 'dir',
                    'path': rel_path,
                    'display_name': item.name
                })
            else:
                # Get file type
                file_type = get_file_type(item.suffix)
                
                # Handle different file types
                if item.suffix == '.md':
                    # Always show markdown files
                    folder_contents.append({
                        'name': item.name,
                        'type': 'md',
                        'path': rel_path,
                        'display_name': item.stem
                    })
                elif file_type and (not images_hidden or file_type != 'images'):
                    # Show other supported files if not hidden
                    folder_contents.append({
                        'name': item.name,
                        'type': file_type,
                        'path': rel_path,
                        'display_name': item.name
                    })
    except Exception as e:
        return f"Error reading folder: {str(e)}", 500

    return render_template('folder.html',
                         folder_path=folder_path,
                         folder_contents=folder_contents,
                         notes_tree=notes_tree,
                         active_path=folder_path.split('/'),
                         current_note=None,
                         breadcrumbs=generate_breadcrumbs(folder_path),
                         allowed_image_extensions=allowed_image_extensions,
                         allowed_file_extensions=allowed_file_extensions)


@md_viewer_bp.route('/serve_stored_image/<path:filename>')
def serve_stored_image(filename):
    # Only used for mode 2 (specific storage folder)
    if '..' in filename or filename.startswith('/'):
        return 'Invalid image path', 400
    storage_path = get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_PATH')
    return send_from_directory(storage_path, filename)

@md_viewer_bp.route('/serve_attatched_image/<path:image_path>')
def serve_attatched_image(image_path):
    # Used to serve images using the configured storage mode
    if '..' in image_path or image_path.startswith('/'):
        return 'Invalid image path', 400
    
    mode = get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_MODE')
    notes_dir = NOTES_FOLDER
    
    if mode == '1':  # Direct in NOTES_DIR
        return send_from_directory(notes_dir, image_path)
    elif mode == '2':  # Specific storage folder
        storage_path = get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_PATH')
        return send_from_directory(storage_path, os.path.basename(image_path))
    elif mode in ['3', '4']:  # In or below note directory
        # For both modes, image path will include note directory path if needed
        return send_from_directory(notes_dir, image_path)


@md_viewer_bp.route('/view/<path:file_path>')
def view_file(file_path):
    """Handle viewing of non-markdown files"""
    try:
        full_path = Path(NOTES_FOLDER) / file_path
        if not full_path.exists() or not full_path.is_file():
            return "File not found", 404

        # Get file type based on extension
        file_type = get_file_type(full_path.suffix)
        if not file_type:
            return "Unsupported file type", 400

        # For images and PDFs, serve the file directly with correct mime type
        if file_type == 'images' or full_path.suffix.lower() == '.pdf':
            mime_type = None
            if file_type == 'images':
                mime_type = 'image/svg+xml' if full_path.suffix == '.svg' else f'image/{full_path.suffix[1:]}'
            elif full_path.suffix.lower() == '.pdf':
                mime_type = 'application/pdf'
            
            return send_from_directory(
                full_path.parent, 
                full_path.name,
                mimetype=mime_type
            )

        # For text files
        if file_type == 'text':
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Only .txt files use the template view
                if full_path.suffix.lower() == '.txt':
                    breadcrumbs = generate_breadcrumbs(file_path)
                    notes_tree = build_tree_structure(NOTES_FOLDER)
                    active_path = get_path_components(file_path)
                    return render_template('view_text.html',
                                        file_name=full_path.name,
                                        content=content,
                                        notes_tree=notes_tree,
                                        active_path=active_path,
                                        breadcrumbs=breadcrumbs)

                # For JSON files, try to pretty print
                if full_path.suffix.lower() == '.json':
                    try:
                        import json
                        parsed = json.loads(content)
                        content = json.dumps(parsed, indent=2, ensure_ascii=False)
                    except json.JSONDecodeError:
                        # If JSON parsing fails, serve as-is
                        pass

                # For YAML files, try to pretty print
                elif full_path.suffix.lower() in ['.yml', '.yaml']:
                    try:
                        import yaml
                        parsed = yaml.safe_load(content)
                        content = yaml.dump(parsed, indent=2, allow_unicode=True)
                    except yaml.YAMLError:
                        # If YAML parsing fails, serve as-is
                        pass

                # For XML files, try to pretty print
                elif full_path.suffix.lower() == '.xml':
                    try:
                        from xml.dom import minidom
                        parsed = minidom.parseString(content)
                        content = parsed.toprettyxml(indent="  ")
                    except Exception:
                        # If XML parsing fails, serve as-is
                        pass

                # All other text files are served as raw text
                return Response(content, 
                              mimetype='text/plain',
                              headers={'Content-Disposition': f'inline; filename="{full_path.name}"'})

            except UnicodeDecodeError:
                return "File cannot be read as text", 400

        return "Unsupported file type", 400

    except Exception as e:
        current_app.logger.error(f"Error viewing file {file_path}: {str(e)}")
        return str(e), 500

@md_viewer_bp.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
            
        folder = request.form.get('folder', '')
        
        # Secure the filename and get extension
        filename = secure_filename(file.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        
        # Get allowed extensions
        allowed_types = get_allowed_file_types()
        all_allowed_extensions = set()
        for extensions in allowed_types.values():
            all_allowed_extensions.update(extensions)
            
        if file_ext not in all_allowed_extensions:
            return jsonify({'error': f'File type {file_ext} not allowed'}), 400
            
        # Create target directory if it doesn't exist
        upload_folder = Path(NOTES_FOLDER) / folder
        upload_folder.mkdir(parents=True, exist_ok=True)
        
        # Save the file temporarily for type verification
        temp_path = upload_folder / f"temp_{filename}"
        file.save(temp_path)
        
        # Verify the file type
        is_valid, actual_type = verify_file_type(temp_path, file_ext)
        
        if not is_valid:
            os.remove(temp_path)  # Clean up temp file
            return jsonify({
                'error': f'File content does not match its extension. '
                        f'Claimed: {file_ext}, Detected: {actual_type}'
            }), 400
            
        # Move to final location
        final_path = upload_folder / filename
        temp_path.rename(final_path)
        
        return jsonify({'message': 'File uploaded successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@md_viewer_bp.route('/download_file')
def download_file():
    """Download a file from the notes directory"""
    try:
        file_path = request.args.get('path')
        if not file_path:
            return "No file specified", 400
            
        full_path = Path(NOTES_FOLDER) / file_path
        
        # Security check - ensure file is within NOTES_FOLDER
        try:
            if not str(full_path.resolve()).startswith(str(Path(NOTES_FOLDER).resolve())):
                return "Invalid file path", 403
        except (ValueError, RuntimeError):
            return "Invalid file path", 403
            
        if not full_path.is_file():
            return "File not found", 404
            
        return send_from_directory(
            full_path.parent, 
            full_path.name,
            as_attachment=True
        )
        
    except Exception as e:
        current_app.logger.error(f"Error downloading file: {str(e)}")
        return str(e), 500


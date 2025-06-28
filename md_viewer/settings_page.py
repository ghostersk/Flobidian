from flask import render_template, request, url_for, jsonify, current_app
from pathlib import Path
import os
from app_settings_loader import get_setting, set_setting
from md_viewer.support_functions import build_tree_structure, check_notes_dir_security, NOTES_FOLDER
from md_viewer import md_viewer_bp


@md_viewer_bp.route('/settings')
def image_storage_settings_page():
    """Show image storage settings page"""
    notes_tree = build_tree_structure(NOTES_FOLDER)
    
    return render_template('settings.html',
                         notes_tree=notes_tree,
                         active_path=[],
                         current_note=None,
                         breadcrumbs=[
                             {'name': '/', 'url': url_for('md_viewer.index')},
                             {'name': 'Settings', 'url': None}
                         ])

@md_viewer_bp.route('/settings/image_storage', methods=['GET', 'POST'])
def image_storage_settings():
    """Handle image storage settings"""
    if request.method == 'POST':
        try:
            mode = request.form.get('storage_mode')
            path = request.form.get('storage_path', '').strip()
            subfolder = request.form.get('subfolder_name', '').strip()

            # Validate mode
            if mode not in ['1', '2', '3', '4']:
                return jsonify({'error': 'Invalid storage mode'}), 400

            # Validate path for mode 2
            if mode == '2' and not path:
                return jsonify({'error': 'Storage path is required for mode 2'}), 400

            # Validate subfolder name for mode 4
            if mode == '4' and not subfolder:
                return jsonify({'error': 'Subfolder name is required for mode 4'}), 400

            # Save settings and update app config
            settings = {
                'IMAGE_STORAGE_MODE': mode,
                'IMAGE_STORAGE_PATH': path if mode == '2' else 'images',
                'IMAGE_SUBFOLDER_NAME': subfolder if mode == '4' else 'attatched'
            }

            # Update settings.ini and app config
            for key, value in settings.items():
                set_setting('MD_NOTES_APP', key, value)
                current_app.config[key] = value

            return jsonify({
                'success': True,
                'message': 'Image storage settings updated successfully',
                'settings': settings,
                'reload_required': True
            })
        except Exception as e:
            current_app.logger.error(f"Error saving image storage settings: {str(e)}")
            return jsonify({'error': str(e)}), 500

    # For GET request, return current settings directly from settings.ini
    try:
        current_settings = {
            'mode': get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_MODE'),
            'path': get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_PATH'),
            'subfolder': get_setting('MD_NOTES_APP', 'IMAGE_SUBFOLDER_NAME')
        }
        return jsonify(current_settings)
    except Exception as e:
        current_app.logger.error(f"Error reading image storage settings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@md_viewer_bp.route('/settings/notes_dir', methods=['GET', 'POST'])
def notes_dir_settings():
    """Handle notes directory settings"""
    if request.method == 'POST':
        try:
            new_dir = request.form.get('notes_dir', '').strip()
            if not new_dir:
                return jsonify({'error': 'Notes directory is required'}), 400

            # Convert to Path and resolve to absolute path
            new_path = Path(new_dir).resolve()

            # Security checks
            is_valid, error_msg = check_notes_dir_security(new_path)
            if not is_valid:
                return jsonify({'error': error_msg}), 400

            # Try to create directory if it doesn't exist
            if not new_path.exists():
                try:
                    os.makedirs(new_path)
                except Exception as e:
                    return jsonify({'error': f'Failed to create directory: {str(e)}'}), 500

            # Verify permissions
            if not os.access(new_path, os.R_OK | os.W_OK):
                return jsonify({'error': 'Directory is not readable and writable'}), 400

            # Update settings.ini and app config
            set_setting('MD_NOTES_APP', 'NOTES_DIR', str(new_path))
            
            # Update the application configuration
            current_app.config['NOTES_DIR'] = new_path
            # Update the global NOTES_FOLDER variable
            global NOTES_FOLDER
            NOTES_FOLDER = new_path
            
            return jsonify({
                'success': True,
                'message': 'Notes directory updated successfully. Reloading page...',
                'notes_dir': str(new_path),
                'reload_required': True  # Signal frontend to reload the page
            })
        except Exception as e:
            current_app.logger.error(f"Error saving notes directory: {str(e)}")
            return jsonify({'error': str(e)}), 500

    # For GET request, return current setting
    try:
        notes_dir = str(get_setting('MD_NOTES_APP', 'NOTES_DIR', fallback='notes'))
        return jsonify({'notes_dir': notes_dir})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@md_viewer_bp.route('/settings/check_notes_dir')
def check_notes_dir():
    """Check if a directory path is valid and accessible"""
    try:
        path = request.args.get('path', '').strip()
        if not path:
            return jsonify({'valid': False, 'error': 'No path provided'})

        # Convert to Path and resolve to absolute path
        test_path = Path(path).resolve()

        # Security check
        is_valid, error_msg = check_notes_dir_security(test_path)
        if not is_valid:
            return jsonify({'valid': False, 'error': error_msg})

        # Check if directory exists
        exists = test_path.exists()
        is_dir = test_path.is_dir() if exists else None

        # If it doesn't exist, check if we can create it
        if not exists:
            try:
                os.makedirs(test_path)
                os.rmdir(test_path)  # Clean up after test
                can_create = True
            except Exception:
                can_create = False
            return jsonify({
                'valid': can_create,
                'error': None if can_create else 'Cannot create directory at this location'
            })

        # If it exists but isn't a directory
        if not is_dir:
            return jsonify({'valid': False, 'error': 'Path exists but is not a directory'})

        # Check permissions
        can_read = os.access(test_path, os.R_OK)
        can_write = os.access(test_path, os.W_OK)

        if not (can_read and can_write):
            return jsonify({
                'valid': False,
                'error': 'Directory exists but is not both readable and writable',
                'can_read': can_read,
                'can_write': can_write
            })

        return jsonify({
            'valid': True,
            'can_read': can_read,
            'can_write': can_write
        })

    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)})

@md_viewer_bp.route('/settings/app', methods=['GET', 'POST'])
def app_settings():
    """Handle application settings"""
    if request.method == 'POST':
        try:
            app_name = request.form.get('app_name', '').strip()
            hide_sidepane = request.form.get('hide_sidepane', '').strip()
            skip_folders = request.form.get('skip_folders', '').strip()
            hide_images = request.form.get('hide_images', 'False')
            allowed_image_extensions = request.form.get('allowed_image_extensions', '').strip()
            allowed_file_extensions = request.form.get('allowed_file_extensions', '').strip()

            # Validate app name
            if not app_name:
                return jsonify({'error': 'Application name is required'}), 400

            # Clean and validate extensions (convert to lowercase and remove spaces)
            if allowed_image_extensions:
                allowed_image_extensions = ','.join(
                    ext.strip().lower() for ext in allowed_image_extensions.split(',') if ext.strip()
                )
            if allowed_file_extensions:
                allowed_file_extensions = ','.join(
                    ext.strip().lower() for ext in allowed_file_extensions.split(',') if ext.strip()
                )

            # Update settings
            settings = {
                'NOTE_APP_NAME': app_name,
                'NOTES_DIR_HIDE_SIDEPANE': hide_sidepane,
                'NOTES_DIR_SKIP': skip_folders,
                'IMAGES_FS_HIDE': hide_images,
                'ALLOWED_IMAGE_EXTENSIONS': allowed_image_extensions,
                'ALLOWED_FILE_EXTENSIONS': allowed_file_extensions
            }

            # Update each setting
            for key, value in settings.items():
                set_setting('MD_NOTES_APP', key, value)
                current_app.config[key] = value

            return jsonify({
                'success': True,
                'message': 'Application settings updated successfully',
                'settings': settings,
                'reload_required': True
            })
        except Exception as e:
            current_app.logger.error(f"Error saving application settings: {str(e)}")
            return jsonify({'error': str(e)}), 500

    # For GET request, return current settings
    try:
        current_settings = {
            'app_name': get_setting('MD_NOTES_APP', 'NOTE_APP_NAME', fallback='My Notes'),
            'hide_sidepane': get_setting('MD_NOTES_APP', 'NOTES_DIR_HIDE_SIDEPANE', fallback=''),
            'skip_folders': get_setting('MD_NOTES_APP', 'NOTES_DIR_SKIP', fallback=''),
            'hide_images': get_setting('MD_NOTES_APP', 'IMAGES_FS_HIDE', fallback='False'),
            'allowed_image_extensions': get_setting('MD_NOTES_APP', 'ALLOWED_IMAGE_EXTENSIONS', 
                                                  fallback='jpg,jpeg,png,gif,bmp'),
            'allowed_file_extensions': get_setting('MD_NOTES_APP', 'ALLOWED_FILE_EXTENSIONS',
                                                 fallback='txt,csv,json,html,htm,xml,yaml,yml,ini,log,js,css,py,md')
        }
        return jsonify(current_settings)
    except Exception as e:
        current_app.logger.error(f"Error reading application settings: {str(e)}")
        return jsonify({'error': str(e)}), 500


# app.py
import os
from flask import Flask, render_template
from werkzeug.exceptions import HTTPException
from pathlib import Path
from md_viewer import md_viewer_bp
from app_settings_loader import (
    ensure_settings_ini, get_setting, FLASK_HOST, FLASK_PORT
)
import logging

# Setup logger
logger = logging.getLogger(__name__)


app = Flask(__name__)
# Ensure settings.ini exists and is up to date on app launch
ensure_settings_ini()

app.config['SECRET_KEY'] = get_setting('FLASK', 'SECRET_KEY',)
app.config['DEBUG'] = get_setting('FLASK', 'DEBUG', type_=bool)
app.config['NOTES_DIR'] = Path(get_setting('MD_NOTES_APP', 'NOTES_DIR')).resolve()
max_content_length = int(get_setting('FLASK', 'MAX_CONTENT_LENGTH')) * 1024 * 1024  # Convert MB to bytes
app.config['MAX_CONTENT_LENGTH'] = max_content_length

# Initialize image storage settings
app.config['IMAGE_STORAGE_MODE'] = get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_MODE')
app.config['IMAGE_STORAGE_PATH'] = get_setting('MD_NOTES_APP', 'IMAGE_STORAGE_PATH')
app.config['IMAGE_SUBFOLDER_NAME'] = get_setting('MD_NOTES_APP', 'IMAGE_SUBFOLDER_NAME')

# Register the md_viewer blueprint
app.register_blueprint(md_viewer_bp)


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
    os.makedirs(app.config['NOTES_DIR'], exist_ok=True)


if __name__ == '__main__':
    app.run(debug=True, host=FLASK_HOST, port=FLASK_PORT)
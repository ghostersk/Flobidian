from flask import Blueprint
import logging

# Create the main blueprint for markdown viewer
md_viewer_bp = Blueprint('md_viewer', __name__, 
                    template_folder='templates',
                    static_folder='static',
                    static_url_path='/md_viewer/static')

# Setup logger
logger = logging.getLogger(__name__)




# Import all routes
from . import viewer  # Has the main viewing routes (/, /note, /folder)
from . import editor  # Has the edit/create/delete routes
from . import settings_page  # Has the settings routes
from . import support_functions  # Contains utility functions used across the app
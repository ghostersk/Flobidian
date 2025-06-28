# Flask application to view Obsidian notes in web browser
- just point the location of your folder with `.md` notes to app with `NOTES_DIR`

## Configuration

This app uses a `settings.ini` file for configuration. On first run, it will be created automatically if missing, and any missing values will be filled in with defaults.

##
- Markdown and code block `https://highlightjs.org/#usage`

## App Summary

- View and browse Obsidian-compatible markdown notes and folders in a web browser
- Supports image and file uploads with configurable allowed extensions and secure type checking
- Edit app settings (including allowed file types) via a web UI
- Hide or skip folders/files as per settings
- Download files and view images, text, and documents (PDF, CSV, JSON, YAML, XML, etc.)
- Drag & drop or button-based file upload, with progress and notifications
- Context menu for file/folder actions (open, download)
- Syntax highlighting for code/text files and pretty-printing for JSON/YAML/XML
- Consistent notification system using a modal
- Sidebar navigation with persistent expand/collapse state
- Multiple image storage modes to match Obsidian's attachment handling
- Secure file handling and upload validation to prevent malicious uploads


## Image storing trying to follow Obsidian settings
Let me break this down step by step to make sure we fix all parts correctly.

First, let me make sure I understand each mode's requirements:

1. Mode 1 (Root directory):
   - Images are stored directly in NOTES_DIR root
   - In .md file: just filename like `![[image.png]]`
   - When showing: serve from NOTES_DIR root

2. Mode 2 (Specific folder):
   - Images stored in IMAGE_STORAGE_PATH
   - In .md file: just filename like `![[image.png]]`
   - When showing: serve from IMAGE_STORAGE_PATH

3. Mode 3 (Same as note):
   - Images stored in same directory as the .md file
   - In .md file: just filename like `![[image.png]]` (since it's in same dir)
   - When showing: serve from note's directory

4. Mode 4 (Subfolder under note):
   - Images stored in IMAGE_SUBFOLDER_NAME under note's directory
   - In .md file: `![[<IMAGE_SUBFOLDER_NAME>/image.png]]`
   - When showing: serve from note's directory/IMAGE_SUBFOLDER_NAME

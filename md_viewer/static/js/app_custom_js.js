// app_custom_js.js
// Replace Obsidian-style ![[...]] with <img> tags in rendered HTML
function renderObsidianImages(container) {
    if (!container) return;
    const obsidianImgRegex = /!\[\[([^\]]+\.(png|jpg|jpeg|gif|webp))\]\]/gi;
    container.innerHTML = container.innerHTML.replace(obsidianImgRegex, function(match, filename) {
        // Use the Flask-provided URL template if available
        let urlTemplate = window.attatchedImageUrlTemplate || "/serve_attatched_image/__IMAGE_PATH__";
        
        // Get storage settings from data attributes
        let storageMode = container.getAttribute('data-storage-mode') || '1';
        let noteDir = container.getAttribute('data-note-dir') || '';
        
        // Clean up the filename to remove any leading slashes and normalize path
        let cleanFilename = filename.replace(/^\/+/, '').replace(/\\/g, '/');
        
        // Construct the image path based on storage mode
        let imagePath;
        if (storageMode === '1') {
            // Mode 1: Direct in NOTES_DIR root
            // Keep full path relative to NOTES_DIR
            imagePath = cleanFilename;
        } else if (storageMode === '2') {
            // Mode 2: Specific storage folder
            // Only use filename as backend serves from storage folder
            imagePath = cleanFilename.split('/').pop();
        } else if (storageMode === '3') {
            // Mode 3: Same directory as note
            if (noteDir) {
                // If image path is absolute (from root), use it as is
                imagePath = cleanFilename.includes('/') ? 
                    cleanFilename : 
                    `${noteDir}/${cleanFilename}`;
            } else {
                // No note directory (shouldn't happen), use filename as is
                imagePath = cleanFilename;
            }
        } else if (storageMode === '4') {
            // Mode 4: In the attatched subfolder under note's directory
            let noteFolder = noteDir || '';
            let subfolder = container.getAttribute('data-storage-base') || 'attatched';
            let finalFilename = cleanFilename.split('/').pop(); // Just the filename
            
            // Build path: note_folder/subfolder/image_name.png
            imagePath = noteFolder ? `${noteFolder}/${subfolder}/${finalFilename}` : `${subfolder}/${finalFilename}`;
        } else {
            // Default to mode 1 behavior - keep full path
            imagePath = cleanFilename;
        }
        
        // Replace placeholder in the template and ensure no double slashes
        let imgUrl = urlTemplate.replace('__IMAGE_PATH__', encodeURIComponent(imagePath))
            .replace(/([^:])\/+/g, '$1/'); // Replace multiple slashes with single slash, except after colon
        return `<img src="${imgUrl}" alt="${filename}" style="max-width:100%;">`;
    });
}

// For note.html (view mode)
document.addEventListener('DOMContentLoaded', function() {
    const noteContent = document.querySelector('.card.card-body');
    if (noteContent) {
        window.renderObsidianImages(noteContent);
    }
});

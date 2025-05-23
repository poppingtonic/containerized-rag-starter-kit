#!/bin/bash

# Backup old files
cp src/App.vue src/App_old.vue
cp src/main.js src/main_old.js

# Move new files into place
mv src/App_new.vue src/App.vue
mv src/main_new.js src/main.js

# Create views directory if it doesn't exist
mkdir -p src/views

echo "Migration complete!"
echo ""
echo "New features added:"
echo "1. Navigation bar with links to all sections"
echo "2. /cache - View all cached queries with feedback"
echo "3. /evaluation - View evaluation metrics and ratings"
echo "4. /export - Export training data in multiple formats"
echo ""
echo "To revert: cp src/App_old.vue src/App.vue && cp src/main_old.js src/main.js"
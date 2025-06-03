#!/bin/bash

# Backup the old app.py
cp app.py app_old.py

# Replace the old app.py with the new modular version
cp app_new.py app.py

echo "Migration complete! The old app.py has been backed up to app_old.py"
echo "The new modular structure is now in place."
echo ""
echo "New structure:"
echo "- models/     - Pydantic models and schemas"
echo "- routes/     - API route handlers"
echo "- services/   - Business logic services"
echo "- utils/      - Utilities and configuration"
echo ""
echo "To revert: cp app_old.py app.py"
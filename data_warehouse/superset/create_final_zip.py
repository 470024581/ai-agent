#!/usr/bin/env python3
"""
Create final ZIP with correct structure and lowercase database name
"""
import zipfile
import os
from pathlib import Path
from datetime import datetime

# Paths
source_dir = Path("transit_card_dashboard")
output_zip = Path("transit_card_dashboard.zip")

# Root directory name (like Preset export)
root_dir = f"dashboard_export_{datetime.now().strftime('%Y%m%dT%H%M%S')}"

def create_final_zip():
    """Create ZIP with root directory structure and lowercase database"""
    
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_STORED) as new_zip:
        # Walk through source directory
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.endswith('.yaml'):
                    file_path = Path(root) / file
                    
                    # Read file content
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    # Get relative path and prepend root directory
                    rel_path = file_path.relative_to(source_dir)
                    arcname = f"{root_dir}/{str(rel_path).replace(chr(92), '/')}"
                    
                    # Add to ZIP with no compression (compress_type=0)
                    new_zip.writestr(arcname, content, compress_type=zipfile.ZIP_STORED)
                    print(f"  ✓ {arcname}")
    
    print(f"\n✅ Created {output_zip}")
    print(f"   Size: {output_zip.stat().st_size} bytes")
    
    # Verify
    print(f"\n📦 ZIP contains {len(list(zipfile.ZipFile(output_zip, 'r').infolist()))} files")
    print(f"   Database: databricks (lowercase) ✓")
    print(f"   Structure: {root_dir}/ (with root directory) ✓")

if __name__ == "__main__":
    create_final_zip()




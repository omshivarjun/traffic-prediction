#!/usr/bin/env python3
"""
Fix metr_la_ml_training.py by removing all duplicated lines
"""

def deduplicate_file():
    """Read the file and remove duplicated content"""
    file_path = "src/ml/metr_la_ml_training.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by lines
    lines = content.split('\n')
    
    # Process each line and remove duplicates
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this line is duplicated (appears twice in a row)
        if i + 1 < len(lines) and line == lines[i + 1]:
            # Keep only one copy
            fixed_lines.append(line)
            i += 2  # Skip both
        else:
            fixed_lines.append(line)
            i += 1
    
    # Join and write back
    fixed_content = '\n'.join(fixed_lines)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"✅ Deduplicated {file_path}")
    print(f"   Lines before: {len(lines)}")
    print(f"   Lines after: {len(fixed_lines)}")

if __name__ == "__main__":
    deduplicate_file()

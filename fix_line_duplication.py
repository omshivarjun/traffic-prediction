#!/usr/bin/env python3
"""
Fix metr_la_ml_training.py by splitting duplicated content within each line
"""

def fix_line_duplication():
    """Fix lines that have duplicated content within the same line"""
    file_path = "src/ml/metr_la_ml_training.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    for line in lines:
        # Remove newline for processing
        line_content = line.rstrip('\n')
        
        if not line_content or line_content.startswith('#') or line_content.strip() in ['', '"""', "'''"]:
            # Keep empty lines, comments, and docstring markers as-is
            fixed_lines.append(line)
            continue
        
        # Check if line content appears to be duplicated
        # Try splitting it in half and see if both halves are the same
        length = len(line_content)
        if length > 10 and length % 2 == 0:  # Only even length can be perfectly duplicated
            mid = length // 2
            first_half = line_content[:mid]
            second_half = line_content[mid:]
            
            if first_half == second_half:
                # Line is duplicated, keep only first half
                fixed_lines.append(first_half + '\n')
                continue
        
        # Not duplicated, keep as is
        fixed_lines.append(line)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)
    
    print(f"✅ Fixed line duplication in {file_path}")

if __name__ == "__main__":
    fix_line_duplication()

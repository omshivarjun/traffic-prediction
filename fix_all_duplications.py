#!/usr/bin/env python3
"""
Fix ALL Python files with line duplication issues
This handles cases where each line has its content duplicated on the same line
"""

import re

def split_duplicated_line(line):
    """Split a line that has duplicated content"""
    line_content = line.rstrip('\n\r')
    
    # Empty lines, keep as-is
    if not line_content or line_content.isspace():
        return line
    
    # Check for exact duplication (line is repeated twice)
    length = len(line_content)
    if length > 10 and length % 2 == 0:
        mid = length // 2
        first_half = line_content[:mid]
        second_half = line_content[mid:]
        
        if first_half == second_half:
            return first_half + '\n'
    
    # Not duplicated
    return line

def fix_file(filepath):
    """Fix a single file"""
    print(f"Processing {filepath}...")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        fixed_lines = [split_duplicated_line(line) for line in lines]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(fixed_lines)
        
        print(f"  ✅ Fixed {filepath}")
        return True
    except Exception as e:
        print(f"  ❌ Error fixing {filepath}: {e}")
        return False

def main():
    files = [
        "src/batch/daily_aggregation_job.py",
        "src/ml/metr_la_ml_training.py",
        "src/validation/data_validator.py"
    ]
    
    print("="*60)
    print("Fixing Python files with line duplication issues")
    print("="*60 + "\n")
    
    results = {}
    for filepath in files:
        results[filepath] = fix_file(filepath)
    
    print("\n" + "="*60)
    print("RESULTS:")
    print("="*60)
    for filepath, success in results.items():
        status = "✅ FIXED" if success else "❌ FAILED"
        print(f"{status}: {filepath}")
    
    if all(results.values()):
        print("\n🎉 All files fixed successfully!")
    else:
        print("\n⚠️  Some files had errors")

if __name__ == "__main__":
    main()

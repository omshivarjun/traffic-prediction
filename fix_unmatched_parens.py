#!/usr/bin/env python3
"""
Remove unmatched closing parentheses from Python files
"""

def fix_unmatched_parens(filepath):
    """Remove lines that are just ')' or '))'"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip lines that are just closing parens (artifacts from deduplication)
        if stripped in [')', '))', ')))', '))))', '))))))']:
            print(f"  Removing standalone paren at line {i+1}: '{stripped}'")
            continue
        fixed_lines.append(line)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)
    
    print(f"✅ Fixed unmatched parens in {filepath}")

if __name__ == "__main__":
    files = [
        "src/ml/metr_la_ml_training.py",
        "src/batch/daily_aggregation_job.py",
        "src/validation/data_validator.py"
    ]
    
    for filepath in files:
        fix_unmatched_parens(filepath)

#!/usr/bin/env python3
"""
Fix Python syntax errors in batch processing files
Removes wildcard imports from functions/methods and moves them to module level
"""

import re

def fix_daily_aggregation_job():
    """Fix src/batch/daily_aggregation_job.py"""
    file_path = "src/batch/daily_aggregation_job.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add explicit PySpark imports at module level (after dataclasses import)
    pyspark_imports = """
# PySpark imports at module level (fixing syntax errors)
from pyspark.sql.functions import (
    col, count, avg, max, min, sum, variance, when, lit, least,
    date_trunc, countDistinct
)
from pyspark.sql.types import *
from pyspark.sql.window import Window
"""
    
    # Insert imports after "from dataclasses import dataclass, asdict"
    content = content.replace(
        "from dataclasses import dataclass, asdict\n\n# Add spark module to path",
        f"from dataclasses import dataclass, asdict\n{pyspark_imports}\n# Add spark module to path"
    )
    
    # Remove wildcard imports from within functions/methods
    # Pattern 1: from pyspark.sql.functions import * (and next line with types)
    content = re.sub(
        r'\n\s+from pyspark\.sql\.functions import \*\n\s+from pyspark\.sql\.types import \*\n',
        '\n',
        content
    )
    
    # Pattern 2: from pyspark.sql.functions import * (and next line with Window)
    content = re.sub(
        r'\n\s+from pyspark\.sql\.functions import \*\n\s+from pyspark\.sql\.window import Window\n',
        '\n',
        content
    )
    
    # Pattern 3: from pyspark.sql.functions import * (standalone)
    content = re.sub(
        r'\n\s+from pyspark\.sql\.functions import \*\n',
        '\n',
        content
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_metr_la_ml_training():
    """Fix src/ml/metr_la_ml_training.py"""
    file_path = "src/ml/metr_la_ml_training.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Fix the corrupted header (lines 1-20 based on error report)
    fixed_lines = ['#!/usr/bin/env python3\n',
                   '"""\n',
                   'METR-LA ML Training Pipeline - Spark MLlib Implementation\n',
                   '\n',
                   'Spark MLlib pipeline for traffic prediction model training\n',
                   '\n',
                   'Features:\n',
                   '- Reads aggregated data from HDFS\n',
                   '- Time-series feature engineering\n',
                   '- Multiple ML algorithms (Linear Regression, Random Forest, GBT)\n',
                   '- Model evaluation and selection\n',
                   '- Model export for predictions\n',
                   '"""\n']
    
    # Keep the rest of the file starting from line 21
    fixed_content = ''.join(fixed_lines) + ''.join(lines[20:])
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"✅ Fixed {file_path}")

def fix_data_validator():
    """Fix src/validation/data_validator.py"""
    file_path = "src/validation/data_validator.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add PySpark types import at module level if not already there
    if "from pyspark.sql.types import" not in content[:500]:
        # Find the imports section and add it
        content = content.replace(
            "import logging\n",
            "import logging\nfrom pyspark.sql.types import *\n"
        )
    
    # Remove wildcard import from within _execute_validation_rule method
    content = re.sub(
        r'(\s+)from pyspark\.sql\.types import \*\n',
        '',
        content
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

if __name__ == "__main__":
    print("Fixing Python syntax errors...\n")
    fix_daily_aggregation_job()
    fix_metr_la_ml_training()
    fix_data_validator()
    print("\n✅ All Python syntax errors fixed!")

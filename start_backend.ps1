# Start backend server
$env:PYTHONPATH="c:\traffic-prediction"
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

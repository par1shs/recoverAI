$ErrorActionPreference = 'Stop'

Write-Host "Setting up PYTHONPATH..."
$env:PYTHONPATH="."

Write-Host "Running Tests..."
pytest tests/

Write-Host "`nGenerating Synthetic Dataset..."
python backend/simulator/generator.py

Write-Host "`nEvaluating Baselines and RecoverAI MVP..."
python backend/simulator/evaluate.py

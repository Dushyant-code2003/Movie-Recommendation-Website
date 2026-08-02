@echo off
cd /d "%~dp0backend"
pip install -r requirements.txt -q
python train_model.py
python app.py

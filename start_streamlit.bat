@echo off
chcp 65001 >nul
cd /d E:\WorkBuddy\amazon-dashboard
C:\Python314\Scripts\streamlit.exe run app.py --server.port 8501 --server.headless true > E:\WorkBuddy\amazon-dashboard\streamlit.log 2>&1

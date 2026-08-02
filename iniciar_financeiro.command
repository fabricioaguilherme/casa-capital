#!/bin/bash
cd /Users/fabricioguilherme/Documents/Claude/Projects/Aplicacoes/financeiro-familiar
python3 -m streamlit run app.py --server.port 8504 --server.address 0.0.0.0 --server.headless true

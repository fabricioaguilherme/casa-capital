#!/bin/bash
# Script para commitar e fazer push da refatoração multi-tenant
cd "$(dirname "$0")"

echo "=== financeiro-familiar: commit multi-tenant ==="
echo ""
echo "--- git status ---"
git status

echo ""
echo "--- git add -A ---"
git add -A

echo ""
echo "--- git commit ---"
git commit -m "feat: multi-tenant com grupos e usuarios_grupo"

echo ""
echo "--- git push origin main ---"
git push origin main

echo ""
echo "=== Concluído! O Streamlit Cloud vai reimplantar automaticamente. ==="
read -p "Pressione Enter para fechar..."

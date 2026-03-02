@echo off
setlocal EnableDelayedExpansion
title FINORA - Sistema Financeiro Avancado

:: ==========================================
:: 1. Solicitando Permissoes de Administrador
:: ==========================================
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo Solicitando privilegios de administrador para garantir portas e operacao do sistema...
    powershell -Command "Start-Process -FilePath '%~dpnx0' -Verb RunAs"
    exit /b
)

:: Garante que estamos na pasta correta apos a elevacao de privilegios
cd /d "%~dp0"

:: ==========================================
:: 2. Interface Visual (Logo ASCII)
:: ==========================================
:: Forca UTF-8 para os caracteres em bloco
chcp 65001 >nul
cls
echo.
echo  ==============================================================
echo   ███████ ██ ███    ██  ██████  ██████   █████  
echo   ██      ██ ████   ██ ██    ██ ██   ██ ██   ██ 
echo   █████   ██ ██ ██  ██ ██    ██ ██████  ███████ 
echo   ██      ██ ██  ██ ██ ██    ██ ██   ██ ██   ██ 
echo   ██      ██ ██   ████  ██████  ██   ██ ██   ██ 
echo.
echo             Sistema Profissional de Gestao Financeira
echo  Versao: 1.0.0                      Status: Multi-Usuario
echo  ==============================================================
echo.
echo [INFO] Inicializando FINORA...
echo.

:: ==========================================
:: 3. Verificacao de Requisitos e Ambiente
:: ==========================================
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao foi detectado no sistema.
    echo [ERRO] Baixe e instale a versao mais recente em: python.org
    pause
    exit /b
)

if not exist .venv (
    echo [*] Configurando ambiente virtual seguro ^(.venv^)...
    python -m venv .venv
)

call .venv\Scripts\activate

:: ==========================================
:: 4. Checagem Inteligente de Dependencias
:: ==========================================
echo [*] Verificando integridade das dependencias do projeto...
python -c "import flask, flask_sqlalchemy, waitress, PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Instalando novos modulos necessarios e atualizando pacotes. Aguarde...
    python -m pip install --upgrade pip >nul 2>&1
    pip install -q -r requirements.txt
    pip install -q Pillow
) else (
    echo [*] Todas as bibliotecas fundamentais ja estao perfeitamente instaladas e disponiveis.
)

if exist "babel.cfg" (
    echo [*] Carregando modulos de idioma e internacionalizacao...
    pybabel compile -d translations >nul 2>&1
)

:: ==========================================
:: 5. Inicializacao do Servidor Web
:: ==========================================
echo.
echo --------------------------------------------------------------
echo [SUCESSO] Sistema inicializado e integrado. Acesso Liberado.
echo --------------------------------------------------------------
echo.
echo O navegador abrira automaticamente utilizando uma porta segura.
echo Para encerrar o sistema completamente, feche esta janela.
echo.

set FLASK_ENV=production
python app.py

echo.
pause
endlocal

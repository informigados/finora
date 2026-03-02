@echo off
echo ==========================================
echo    Finora - Execucao de Testes
echo ==========================================

REM Verifica se o Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado. Por favor instale o Python.
    pause
    exit /b
)

REM Verifica se o ambiente virtual existe
if not exist .venv (
    echo [INFO] Criando ambiente virtual ^(.venv^)...
    python -m venv .venv
    echo [INFO] Ambiente virtual criado.
)

REM Ativa o ambiente virtual
echo [INFO] Ativando ambiente virtual...
call .venv\Scripts\activate

REM Instala dependencias
if exist requirements.txt (
    echo [INFO] Verificando dependencias...
    pip install -r requirements.txt
) else (
    echo [ERRO] Arquivo requirements.txt nao encontrado!
    pause
    exit /b
)

REM Executa os testes
echo [INFO] Executando testes unitarios com Pytest...
echo.
python -m pytest tests/

echo.
if %errorlevel% equ 0 (
    echo [SUCESSO] Todos os testes passaram!
) else (
    echo [FALHA] Alguns testes falharam. Verifique a saida acima.
)

pause

@echo off
setlocal
title Finora - Criar Executavel (Build)

echo.
echo ==========================================
echo    FINORA - COMPILADOR CROSS-PLATFORM
echo ==========================================
echo.
echo [INFO] Este script vai gerar um executavel independente usando PyInstaller.
echo.

REM 1. Verifica Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado. Instale o Python para continuar.
    pause
    exit /b
)

REM 2. Configura e Ativa Ambiente Virtual
if not exist .venv (
    echo [SETUP] Criando ambiente virtual...
    python -m venv .venv
)

echo [INFO] Ativando ambiente virtual...
call .venv\Scripts\activate

REM 3. Instala dependencias de build e do sistema
echo [INFO] Instalando dependencias do sistema e ferramentas de build...
pip install -q -r requirements.txt
pip install -q pyinstaller pyinstaller-hooks-contrib Pillow

REM 4. Compila Traducoes
echo [INFO] Compilando arquivos de traducao...
pybabel compile -d translations
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao compilar traducoes.
    pause
    exit /b
)

REM 5. Limpa builds anteriores
echo [INFO] Limpando versoes antigas...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "dist_setup" rmdir /s /q "dist_setup"

REM 6. Verifica arquivos obrigatorios de build
if not exist "Finora.spec" (
    echo [ERRO] Arquivo Finora.spec nao encontrado.
    echo Verifique se o arquivo de configuracao do PyInstaller existe na raiz do projeto.
    pause
    exit /b
)

if not exist "static\favicon.ico" (
    echo [ERRO] Icone static\favicon.ico nao encontrado.
    pause
    exit /b
)

REM 7. Executa PyInstaller com build limpo (deterministico)
echo [INFO] Iniciando PyInstaller...
echo Isso pode demorar alguns minutos. Aguarde...
echo.

pyinstaller --noconfirm --clean "Finora.spec"

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Falha durante a compilacao.
    pause
    exit /b
)

if not exist "dist\Finora\Finora.exe" (
    echo.
    echo [ERRO] Build concluido sem gerar dist\Finora\Finora.exe
    pause
    exit /b
)

echo.
echo ==========================================
echo [SUCESSO] Build concluido com perfeicao!
echo ==========================================
echo O arquivo executavel esta localizado na pasta: dist\Finora\
echo.
pause
endlocal

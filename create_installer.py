import os
import sys
import subprocess
import shutil

def run_command(cmd, cwd=None):
    print(f"Executando: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, text=True, shell=True)
    if result.returncode != 0:
        print(f"Erro ao executar comando: {cmd}")
        sys.exit(result.returncode)

def main():
    print("=" * 50)
    print("FINORA - CRIADOR DE INSTALADOR PROFISSIONAL")
    print("=" * 50)
    
    # 1. Gerar o executável stand-alone via PyInstaller usando o build_exe.bat
    if not os.path.exists("build_exe.bat"):
        print("Arquivo build_exe.bat nao encontrado.")
        sys.exit(1)
        
    print("\n[Passo 1/2] Compilando arquivos Python em executavel...")
    # Executa o batch script
    run_command(["build_exe.bat"])
    
    # Verifica se a pasta dist/Finora foi gerada corretamente
    if not os.path.exists(os.path.join("dist", "Finora", "Finora.exe")):
        print("\nErro: dist/Finora/Finora.exe nao foi gerado. Falha na etapa do PyInstaller.")
        sys.exit(1)
        
    # 2. Gerar o instalador via Inno Setup
    print("\n[Passo 2/2] Construindo Setup (Finora_Setup.exe)...")
    
    # Procura o Inno Setup no sistema
    inno_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe"
    ]
    
    iscc = None
    for p in inno_paths:
        if os.path.exists(p):
            iscc = p
            break
            
    if not iscc:
        print("\nErro: Inno Setup (ISCC.exe) nao foi encontrado no sistema.")
        print("Por favor, instale o Inno Setup 6 (https://jrsoftware.org/isinfo.php) para gerar o instalador.")
        sys.exit(1)
        
    iss_file = "finora_installer.iss"
    if not os.path.exists(iss_file):
        print(f"\nErro: Script do instalador ({iss_file}) nao encontrado.")
        sys.exit(1)
        
    run_command([f'"{iscc}"', iss_file])
    
    setup_file = os.path.join(os.getcwd(), "dist_setup", "Finora_Setup_v1.0.0.exe")
    if os.path.exists(setup_file):
        print("=" * 50)
        print("[SUCESSO] Instalador gerado com exito!")
        print(f"Localizacao: {setup_file}")
        print("=" * 50)
    else:
        print("\n[FALHA] Instalador nao foi gerado.")

if __name__ == "__main__":
    main()

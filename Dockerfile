# Use uma imagem oficial do Python como base
FROM python:3.12-slim

# Defina o diretório de trabalho no container
WORKDIR /app

# Defina variáveis de ambiente para otimizar o Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instale dependências do sistema necessárias (ex: gcc para compilar pacotes)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copie os arquivos de requisitos e instale as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie o restante do código da aplicação
COPY . .

# Compile as traduções (caso não estejam compiladas)
RUN pybabel compile -d translations

# Exponha a porta que a aplicação usará
EXPOSE 5000

# Comando para rodar a aplicação usando Gunicorn (servidor de produção)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:create_app('production')"]

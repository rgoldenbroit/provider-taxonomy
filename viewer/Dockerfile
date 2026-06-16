# Minimal static server for the single-file viewer on Cloud Run.
FROM python:3.12-slim
WORKDIR /app
COPY taxonomy.html /app/index.html
# Cloud Run injects PORT (default 8080); serve the generated viewer at /.
CMD ["sh", "-c", "exec python -m http.server ${PORT:-8080}"]

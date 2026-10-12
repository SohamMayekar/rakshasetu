# One image, three processes: api (uvicorn), worker, ticker (PRD §12.1).
FROM public.ecr.aws/docker/library/python:3.12-slim

# Optional extra CAs for TLS-intercepting networks (infra/certs/*.crt; empty on a normal laptop).
COPY --from=certs . /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates >/dev/null 2>&1 || true
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# ffmpeg transcodes voice clips to 16 kHz mono WAV (PRD F-L2).
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY pyproject.toml ./
RUN python -c "import tomllib; p=tomllib.load(open('pyproject.toml','rb'))['project']; \
open('/tmp/req.txt','w').write('\n'.join(p['dependencies'] + p['optional-dependencies']['dev']))" \
    && pip install --no-cache-dir -r /tmp/req.txt
COPY . .
RUN pip install --no-cache-dir --no-deps -e .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

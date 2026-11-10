FROM python:3.12-slim-trixie AS base
ENV APP_ENV=production PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
WORKDIR /app/Backend
COPY Backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY Backend/app ./app
RUN useradd --create-home --uid 10001 platform && mkdir -p /home/platform/runtime && chown -R platform:platform /home/platform
ENV RUNTIME_DIRECTORY=/home/platform/runtime

FROM base AS api
USER platform
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

FROM debian:trixie-slim AS terraform
ARG TERRAFORM_VERSION=1.17.1
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl unzip \
	&& cd /tmp \
	&& curl -fsSLO "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip" \
	&& curl -fsSLO "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_SHA256SUMS" \
	&& grep " terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip$" "terraform_${TERRAFORM_VERSION}_SHA256SUMS" | sha256sum -c - \
	&& unzip "terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip" -d /usr/local/bin

FROM base AS worker
COPY --from=terraform /usr/local/bin/terraform /usr/local/bin/terraform
COPY --chown=platform:platform Terraform/modules /app/Terraform/modules
COPY --chown=platform:platform Terraform/environments/dev/*.tf /app/Terraform/environments/dev/
COPY --chown=platform:platform Terraform/environments/dev/.terraform.lock.hcl /app/Terraform/environments/dev/.terraform.lock.hcl
USER platform
CMD ["python", "-m", "app.worker"]
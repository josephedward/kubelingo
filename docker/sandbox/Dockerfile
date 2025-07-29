# Dockerfile for Kubelingo container sandbox
FROM alpine:3.17

# Install shell and editor dependencies
RUN apk add --no-cache bash vim curl openssl

# Install kubectl v1.24.0
ARG KUBECTL_VERSION=v1.24.0
RUN curl -LO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

# Set a simple prompt for the container shell
RUN echo 'PS1="(kubelingo-container)$ "' >> /etc/profile

# Set working directory
WORKDIR /workspace

ENTRYPOINT ["bash", "--login"]
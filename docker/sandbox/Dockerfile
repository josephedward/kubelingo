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

ENTRYPOINT ["bash", "--login"]FROM alpine:latest

LABEL description="Kubelingo sandbox environment with kubectl and other tools."

# Define kubectl version and target architecture
ARG KUBECTL_VERSION=v1.24.0
ARG TARGETARCH=amd64

# Install dependencies
RUN apk add --no-cache bash vim curl openssl

# Install kubectl
RUN curl -L "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" -o /usr/local/bin/kubectl && \
    chmod +x /usr/local/bin/kubectl

# Set a custom prompt for the container shell
ENV PS1="(kubelingo-container)$ "

# Create a workspace directory. The host CWD will be mounted here.
RUN mkdir /workspace
WORKDIR /workspace

# The default command is to launch a bash shell
CMD ["/bin/bash", "--login"]

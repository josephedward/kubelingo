FROM alpine:latest

LABEL description="Kubelingo sandbox environment with kubectl and other tools."

# Define kubectl version and target architecture
ARG KUBECTL_VERSION=v1.30.2
ARG TARGETARCH=amd64

# Install dependencies
RUN apk add --no-cache bash vim curl openssl

# Install kubectl
RUN curl -L "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" -o /usr/local/bin/kubectl && \
    chmod +x /usr/local/bin/kubectl

# Set a custom prompt for the container shell by adding a script to profile.d
RUN echo 'export PS1="(kubelingo-container)$ "' > /etc/profile.d/kubelingo.sh

# Create a workspace directory. The host CWD will be mounted here.
RUN mkdir /workspace
WORKDIR /workspace

# The default command is to launch a bash shell
CMD ["/bin/bash", "--login"]

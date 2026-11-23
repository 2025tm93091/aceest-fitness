# Jenkins controller for running the ACEest pipeline on a laptop.
# Adds the Docker CLI (talks to the host Docker engine through the mounted socket),
# kubectl (deploys to Minikube) and curl.
FROM jenkins/jenkins:lts-jdk21

USER root
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSLo /usr/local/bin/kubectl \
       "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && rm -rf /var/lib/apt/lists/*
# Runs as root only because this is a local single-user demo that needs the Docker socket.

# ACEest Fitness & Gym — Assignment 2 Report
**Kubernetes Deployment Strategies, SonarQube and Docker Hub CI/CD**

Student: Bhanu Prakash (2025tm93091) · Course: Introduction to DevOps · BITS Pilani WILP
Repository: https://github.com/2025tm93091/aceest-fitness
Docker Hub: https://hub.docker.com/r/2025tm93091/aceest-fitness
Cluster endpoints: Rolling `http://192.168.49.2:30080` · Blue-Green `http://192.168.49.2:30081` ·
Ingress hosts `canary.aceest.local`, `ab.aceest.local`, `shadow.aceest.local`

---

## 1. Objective and scope

Assignment 1 delivered a modular Flask API (`app.py`, `core.py`, `db.py`, `report.py`) with a
56-test pytest suite, a hardened Docker image and CI pipelines in GitHub Actions and Jenkins.
Assignment 2 extends that code base into a production-style continuous delivery system:

- versioned container images published to **Docker Hub**;
- deployment to a **Kubernetes (Minikube)** cluster;
- five release strategies — **Rolling Update, Blue-Green, Canary, A/B Testing and Shadow**;
- static code analysis and a quality gate with **SonarQube**;
- a **Jenkins** pipeline that polls Git, builds, tests, scans, pushes, deploys, smoke-tests,
  archives build artifacts and **rolls back automatically** on failure.

The application itself gained a `GET /version` endpoint (version, variant and pod name, all
injected at build or deploy time) so that each strategy can be observed from the command line.
The test suite now has 58 tests (97 % coverage).

## 2. Architecture

```
 Developer ──push──▶ GitHub ──▶ GitHub Actions: lint → test → docker build → K8s manifest
    │                  │                         validation → push image to Docker Hub
    │                  └──pollSCM (5 min)──▶ Jenkins (Docker on laptop)
    │                        Checkout → Lint → Unit tests (JUnit + coverage.xml)
    │                        → SonarQube analysis → Quality Gate → Build image vN
    │                        → Push to Docker Hub → Deploy (chosen strategy) → Smoke test
    │                        → Archive artifacts      (failure ⇒ automatic rollback)
    ▼
 Docker Hub (aceest-fitness:v1, v2, vN, latest) ──pull──▶ Minikube, namespace "aceest"
                                                         NodePort services + NGINX Ingress
```
*[Insert architecture diagram screenshot here]*

Key design choices:

- **One image, many releases.** The version is a Docker build argument (`APP_VERSION`); the
  variant (blue, green, canary, A, B, shadow…) is a Kubernetes environment variable. The
  same image is promoted unchanged from test to production.
- **Readiness and liveness probes** on `/health` gate traffic, so rolling and blue-green
  switches never send requests to a pod that is not ready.
- **Resource requests/limits** on every pod keep several strategies running together on a
  single-node Minikube cluster.
- **Versioning.** Lecturer versions are kept in `versions/`; releases of the Flask service are
  Git tags (`v1.0.0`, `v2.0.0`) and matching Docker Hub tags, plus one image tag per Jenkins build.
- **One deploy script** (`scripts/deploy.sh`) is used both by hand and by Jenkins, so the
  release process is identical in every environment.

## 3. Deployment strategies

| Strategy | Mechanism in this project | Rollback |
|---|---|---|
| Rolling Update | 4 replicas, `maxSurge 1`, `maxUnavailable 0`; `kubectl set image` replaces pods one at a time | `kubectl rollout undo` |
| Blue-Green | Two full Deployments (`aceest-blue`, `aceest-green`); the Service selector points to the live colour and is patched to switch | Patch the selector back (instant) |
| Canary | Stable v1 (4 pods) and canary v2 (1 pod) behind NGINX Ingress; `canary-weight: 20` sends ~20 % of traffic to v2, raised step by step | Scale canary to 0 |
| A/B Testing | NGINX routes requests carrying header `X-Variant: B` or cookie `ab_variant_b` to version B; everyone else gets A | Delete the B ingress |
| Shadow | NGINX `mirror-target` copies every production request to the shadow v2; its responses are discarded, users only see v1 | Scale shadow to 0 |

*[Insert screenshots: rolling rollout + history; blue/green before-after; 20 canary responses;
A/B three responses; shadow responses + shadow pod log]*

## 4. Code quality — SonarQube

SonarQube (LTS Community) runs as a container. `sonar-project.properties` defines the sources,
the test file and the coverage (`coverage.xml`) and test (`test-results.xml`) reports produced
by the Jenkins *Unit Tests* stage. The *Quality Gate* stage waits for SonarQube's webhook and
aborts the pipeline if the gate fails, so code that does not meet the standard never reaches
Docker Hub or the cluster.

*[Insert SonarQube dashboard: quality gate, coverage, bugs, code smells]*

## 5. Jenkins pipeline

Jenkins and SonarQube run as Docker containers on the developer laptop (`local/docker-compose.yml`),
alongside Minikube. Jenkins uses the host Docker engine through the mounted socket and joins the
`minikube` Docker network to reach the cluster API.

`pollSCM('H/5 * * * *')` checks GitHub every five minutes. A GitHub webhook was not usable because
Jenkins runs on a laptop that is not reachable from the internet. Parameters select the deployment
strategy, Docker Hub user and stable tag. Credentials (`dockerhub-creds`, `kubeconfig`, Sonar
token) are kept in the Jenkins credential store and never in the repository. Every build
archives a versioned source bundle `aceest-fitness-vN.tar.gz` together with test and coverage
reports. If a deployment or smoke test fails, the `post { failure }` block runs the rollback
for the selected strategy.

*[Insert Jenkins stage view, test trend, archived artifacts, "Started by an SCM change"]*

## 6. Challenges and resolutions

| Challenge | Resolution |
|---|---|
| Jenkins runs in Docker and drives the host Docker engine, so workspace bind mounts point at the wrong filesystem | Tests run in a container created from the CI image; `docker cp` copies the test file in and the JUnit/coverage reports out, and the coverage source path is rewritten for SonarQube |
| SQLite could not write inside a read-only or foreign-owned app directory | Database path set through `ACEEST_DB_PATH=/tmp/...` in the image |
| Telling releases apart during canary, A/B and shadow tests | Added `/version` returning version, variant and pod name |
| Jenkins could not use Minikube's default kubeconfig (certificate file paths, 127.0.0.1 address) | Flattened kubeconfig with the server rewritten to the Minikube IP (`https://192.168.49.2:8443`), stored as a Jenkins secret-file credential |
| GitHub webhooks cannot reach the private VM | SCM polling every 5 minutes |
| `deploy.sh` broke when committed from Windows (CRLF line endings) | `.gitattributes` forces LF for scripts and YAML |
| Ingress on Minikube with the Docker driver (Windows) | `minikube addons enable ingress` plus `minikube tunnel`; hosts selected with the `Host` header |

## 7. Outcomes

- Five release strategies, each with a tested rollback path, defined as code under `k8s/`.
- End-to-end automated pipeline from commit to running pods, with a SonarQube quality gate.
- Versioned, reproducible images on Docker Hub, and archived build artifacts for every build.
- GitHub Actions additionally validates all 24 Kubernetes objects against the API schema on
  every push.

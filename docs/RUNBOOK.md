# Assignment 2 — Runbook (do these in order)

Replace `YOUR_DOCKERHUB_USER` with your Docker Hub username everywhere below.
Windows commands are for **PowerShell**; `bash scripts/deploy.sh …` lines run in **Git Bash**
(installed with Git for Windows) or on the Prayogsala VM.

> PowerShell tip: use `curl.exe`, not `curl` (`curl` is an alias for `Invoke-WebRequest`).

---

## 0. Get the new files into your repo

```powershell
cd C:\dev\aceest-fitness
git pull                                  # make sure you are up to date
# unzip aceest-assignment2.zip over the folder (overwrite when asked)
# copy the lecturer's Aceestver-*.py files into the new versions\ folder
#   (the brief asks for "ACEest_Fitness.py and versions" in the project folder), then:
.\venv\Scripts\Activate.ps1
pytest -q                                 # expect: 58 passed
git checkout -b feature/assignment-2
git add .
git commit -m "feat(k8s): add 5 deployment strategies, SonarQube and Docker Hub pipeline"
git push -u origin feature/assignment-2
# open a Pull Request on GitHub -> merge into main once Actions is green
```

---

## 1. Docker Hub — build and push two versions

You signed in to Docker Hub with Google, so:
- Your **Docker Hub username is not your email**. Find it at hub.docker.com → click your avatar
  (top right) — the name shown there (also in the URL `hub.docker.com/u/<username>`) is
  `YOUR_DOCKERHUB_USER`.
- Google accounts have **no Docker password** — `docker login` needs a **Personal Access Token**.

1. hub.docker.com → **Create repository** `aceest-fitness` (Public).
2. Avatar → **Account settings → Personal access tokens → Generate new token**
   (access: Read, Write, Delete). Copy it — it is shown only once.

```powershell
docker login -u YOUR_DOCKERHUB_USER          # Password: paste the access token (not your Google password)
docker build --build-arg APP_VERSION=1.0.0 -t YOUR_DOCKERHUB_USER/aceest-fitness:v1 .
docker build --build-arg APP_VERSION=2.0.0 -t YOUR_DOCKERHUB_USER/aceest-fitness:v2 .
docker push YOUR_DOCKERHUB_USER/aceest-fitness:v1
docker push YOUR_DOCKERHUB_USER/aceest-fitness:v2

docker tag YOUR_DOCKERHUB_USER/aceest-fitness:v2 YOUR_DOCKERHUB_USER/aceest-fitness:latest
docker push YOUR_DOCKERHUB_USER/aceest-fitness:latest

git tag -a v1.0.0 d304857 -m "Release 1.0.0 - Assignment 1 baseline" ; git push origin v1.0.0
git tag -a v2.0.0 -m "Release 2.0.0 - Kubernetes deployment strategies" ; git push origin v2.0.0
```
(Run the `v2.0.0` tag after your Assignment 2 commit is merged into main.) Every Jenkins build
adds another image tag (`v<build-number>`), so the Docker Hub repo ends up holding all versions,
which the brief asks for.

GitHub repo → Settings → Secrets and variables → Actions → add `DOCKERHUB_USERNAME`
and `DOCKERHUB_TOKEN` so the **Push to Docker Hub** job also publishes on every push to main.

📸 Docker Hub repo page showing tags `v1`, `v2`.

---

## 2. Minikube cluster

```powershell
winget install Kubernetes.minikube
winget install -e --id Kubernetes.kubectl
# close and reopen PowerShell, then:
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable ingress
kubectl get nodes                            # STATUS = Ready
kubectl get pods -n ingress-nginx            # controller = Running
```

For the Ingress-based strategies (Canary, A/B, Shadow), open a **second PowerShell as
Administrator** and leave this running:

```powershell
minikube tunnel
```

📸 `kubectl get nodes` + ingress controller running.

---

## 3. The five deployment strategies

All objects live in the `aceest` namespace. Run each block, capture the screenshots,
then move on (they can all run together).

### 3.1 Rolling update
```bash
bash scripts/deploy.sh rolling YOUR_DOCKERHUB_USER v1     # baseline v1 (4 pods)
bash scripts/deploy.sh rolling YOUR_DOCKERHUB_USER v2     # rolls pods 1-by-1 to v2
```
```powershell
kubectl -n aceest rollout history deployment/aceest-rolling
minikube service aceest-rolling -n aceest --url           # keep window open, copy URL
curl.exe -s http://127.0.0.1:<port>/version               # -> "version": "2.0.0"
kubectl -n aceest rollout undo deployment/aceest-rolling  # rollback demo -> 1.0.0
```
📸 rollout status, rollout history, /version before & after, rollback.

### 3.2 Blue-Green
```bash
bash scripts/deploy.sh blue-green YOUR_DOCKERHUB_USER v2  # green gets v2, traffic switched
```
```powershell
minikube service aceest-bluegreen -n aceest --url
curl.exe -s http://127.0.0.1:<port>/version               # variant "green", 2.0.0
kubectl -n aceest get svc aceest-bluegreen -o jsonpath="{.spec.selector}"
```
```bash
bash scripts/deploy.sh rollback YOUR_DOCKERHUB_USER blue-green   # instant switch back to blue
```
📸 version before switch (blue), after switch (green), after rollback (blue).

### 3.3 Canary (20 % to v2)
```bash
bash scripts/deploy.sh canary YOUR_DOCKERHUB_USER v2 v1
```
```powershell
1..20 | % { curl.exe -s -H "Host: canary.aceest.local" http://127.0.0.1/version; "" }
# ~4 of 20 responses show "variant": "canary"
kubectl -n aceest annotate ingress aceest-canary nginx.ingress.kubernetes.io/canary-weight=50 --overwrite
```
📸 the 20 responses showing the stable/canary mix.

### 3.4 A/B testing (header / cookie)
```bash
bash scripts/deploy.sh ab-testing YOUR_DOCKERHUB_USER v2 v1
```
```powershell
curl.exe -s -H "Host: ab.aceest.local" http://127.0.0.1/version                          # A
curl.exe -s -H "Host: ab.aceest.local" -H "X-Variant: B" http://127.0.0.1/version        # B
curl.exe -s -H "Host: ab.aceest.local" --cookie "ab_variant_b=always" http://127.0.0.1/version  # B
```
📸 the three responses.

### 3.5 Shadow (mirrored traffic)
```bash
bash scripts/deploy.sh shadow YOUR_DOCKERHUB_USER v2 v1
```
```powershell
1..5 | % { curl.exe -s -H "Host: shadow.aceest.local" http://127.0.0.1/version; "" }   # always production
kubectl -n aceest logs deploy/aceest-shadow --tail=50 | Select-String "/version"   # the same 5 requests appear here
```
📸 responses (all production) + shadow pod log showing the mirrored requests.

Overview screenshot: `kubectl -n aceest get deploy,svc,ingress -o wide`

---

## 4. SonarQube

```powershell
docker run -d --name sonarqube -p 9000:9000 sonarqube:lts-community
```
(On the Linux VM first run: `sudo sysctl -w vm.max_map_count=524288`.)

1. Open http://localhost:9000 → login `admin` / `admin` → set new password.
2. **Create project** → Manually → key `aceest-fitness` → Locally → generate a **token**.
3. Administration → Configuration → **Webhooks** → Create:
   `http://<jenkins-host>:8080/sonarqube-webhook/` (needed for the Quality Gate stage).

Quick scan from the laptop (no Jenkins needed):
```powershell
pytest --cov=core --cov=db --cov=report --cov=app --cov-report=xml:coverage.xml --junitxml=test-results.xml
docker run --rm -e SONAR_HOST_URL=http://host.docker.internal:9000 -e SONAR_TOKEN=<token> `
  -v "${PWD}:/usr/src" sonarsource/sonar-scanner-cli
```
Save the SonarQube report into the repo (a submission deliverable):
```powershell
curl.exe -u "<token>:" "http://localhost:9000/api/measures/component?component=aceest-fitness&metricKeys=alert_status,bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,ncloc,security_hotspots" -o reports/sonarqube-report.json
```
📸 SonarQube project dashboard (Quality Gate Passed, coverage %, bugs/code smells) — also save it
as `reports/sonarqube-dashboard.png` and commit both files.

---

## 5. Jenkins pipeline (Prayogsala VM)

1. **Plugins:** SonarQube Scanner, Docker Pipeline, Credentials Binding, JUnit, Timestamper, Pipeline, Git.
2. **kubectl on the VM:** `sudo dnf install -y kubectl` (or download the binary) – needed by the deploy stage.
3. **Credentials** (Manage Jenkins → Credentials → Global):
   - `dockerhub-creds` — *Username with password*: Docker Hub user + access token.
   - `kubeconfig` — *Secret file*. Create it where minikube runs:
     `kubectl config view --flatten --minify > kubeconfig-jenkins.yaml` and upload it.
4. **SonarQube server:** Manage Jenkins → System → SonarQube servers → Name `sonarqube`,
   URL `http://localhost:9000`, token = *Secret text* credential with the Sonar token.
5. **Scanner tool:** Manage Jenkins → Tools → SonarQube Scanner → Name `sonar-scanner`, install automatically.
6. **Job:** New Item → `aceest-fitness-cd` → Pipeline → *Pipeline script from SCM* → Git →
   `https://github.com/2025tm93091/aceest-fitness.git`, branch `*/main`, Script Path `Jenkinsfile`.
7. First run: **Build Now** (it registers the parameters). Then **Build with Parameters** →
   set `DOCKERHUB_USER`, pick a `DEPLOY_STRATEGY`.
   No cluster reachable from Jenkins? tick `SKIP_DEPLOY` – build/test/scan/push still run.

The pipeline polls GitHub every 5 minutes (`pollSCM`), because GitHub webhooks can't reach a
private VM address. Push a commit and show the build starting with "Started by an SCM change".

📸 Stage View all green, Test Result trend, SonarQube link on the build, archived artifacts
(`aceest-fitness-vN.tar.gz`), console line "Started by an SCM change".

---

## 6. Endpoint URL for the report

```powershell
minikube service aceest-bluegreen -n aceest --url     # e.g. http://192.168.49.2:30081
minikube service aceest-rolling   -n aceest --url     # e.g. http://192.168.49.2:30080
```
Ingress hosts: `canary.aceest.local`, `ab.aceest.local`, `shadow.aceest.local` → `minikube ip`.

---

## 7. Submission checklist (from the Assignment 2 brief)

- [ ] Public GitHub repo with: Flask app + `versions/` (lecturer versions), `Jenkinsfile`,
      `Dockerfile`, `k8s/` manifests, `test_app.py`, `reports/` (SonarQube report)
- [ ] Commits, branch (`feature/assignment-2`), PR and tags `v1.0.0`, `v2.0.0`
- [ ] Docker Hub repo `YOUR_DOCKERHUB_USER/aceest-fitness` with tags `v1`, `v2`, `latest`, `vN`
- [ ] Jenkins: successful runs for recent commits ("Started by an SCM change"), tests run in the container
- [ ] SonarQube quality gate result
- [ ] Endpoint URLs of the running cluster for all 5 strategies (section 6)
- [ ] 2–3 page report (`docs/REPORT.md`) with screenshots, exported as PDF

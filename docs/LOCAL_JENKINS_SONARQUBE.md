# Jenkins + SonarQube on your laptop (instead of Prayogsala)

Both run as Docker containers next to Minikube. Takes about 45 minutes.
Run everything from your repo folder in PowerShell unless stated otherwise.
Keep Minikube running (`minikube status`) before you start.

---

## 1. Push the updated files

```powershell
git checkout main ; git pull
# extract the new zip over the repo folder (Replace when asked)
git checkout -b feature/local-ci
git add .
git commit -m "ci(jenkins): run tests in containers without volume mounts; add local Jenkins+SonarQube stack"
git push -u origin feature/local-ci
# GitHub: open PR -> wait for green checks -> Merge into main
git checkout main ; git pull
```

## 2. Start Jenkins and SonarQube

```powershell
cd local
docker compose up -d --build        # first time: 5-10 min (downloads images)
docker compose ps                   # both "running"
cd ..
```
If you get `network minikube declared as external, but could not be found` → start Minikube first.

## 3. SonarQube (http://localhost:9001 — 9001 because Zscaler uses 9000)

1. Login `admin` / `admin` → set a new password. (First start takes 1-2 min; refresh until the login page appears.)
2. Avatar (top right) → **My Account → Security → Generate Token**:
   name `jenkins`, type **Global Analysis Token** → **copy it**.
3. **Administration → Configuration → Webhooks → Create**:
   Name `jenkins`, URL `http://jenkins:8080/sonarqube-webhook/` → Create.

📸 webhook page.

## 4. Jenkins first start (http://localhost:8080)

```powershell
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```
Paste the password → **Install suggested plugins** → create your admin user.

**Manage Jenkins → Plugins → Available plugins** → tick **SonarQube Scanner** and
**Docker Pipeline** → Install → tick "Restart Jenkins when installation is complete".

## 5. kubeconfig for Jenkins (lets Jenkins deploy to Minikube)

Create it **outside the repo** (it contains cluster keys):
```powershell
cd $HOME
kubectl config view --flatten --minify --context minikube | Out-File -Encoding ascii kubeconfig-jenkins.yaml
(Get-Content kubeconfig-jenkins.yaml) -replace 'server: https://127\.0\.0\.1:\d+', 'server: https://192.168.49.2:8443' | Set-Content -Encoding ascii kubeconfig-jenkins.yaml
Select-String "server:" kubeconfig-jenkins.yaml          # must show https://192.168.49.2:8443

# prove Jenkins can reach the cluster
docker cp kubeconfig-jenkins.yaml jenkins:/tmp/kc
docker exec jenkins kubectl --kubeconfig /tmp/kc get nodes      # minikube   Ready
```
(`192.168.49.2` is your `minikube ip` — the ADDRESS column in your ingress screenshot.)

## 6. Jenkins credentials and tools

**Manage Jenkins → Credentials → System → Global credentials → Add Credentials**:

| Kind | ID | Value |
|---|---|---|
| Username with password | `dockerhub-creds` | Username `2025tm93091`, Password = Docker Hub access token |
| Secret text | `sonar-token` | the SonarQube token from step 3 |
| Secret file | `kubeconfig` | upload `C:\Users\<you>\kubeconfig-jenkins.yaml` |

**Manage Jenkins → System → SonarQube servers** → tick *Environment variables* →
**Add SonarQube**: Name `sonarqube`, Server URL `http://sonarqube:9000`, token `sonar-token` → Save.

**Manage Jenkins → Tools → SonarQube Scanner installations → Add**:
Name `sonar-scanner`, tick *Install automatically* → Save.

## 7. Create and run the pipeline

**New Item** → `aceest-fitness-cd` → **Pipeline** → OK →
- Pipeline → Definition: **Pipeline script from SCM** → SCM **Git**
- Repository URL `https://github.com/2025tm93091/aceest-fitness.git`
- Branch `*/main`, Script Path `Jenkinsfile` → Save.

Click **Build Now** (runs with defaults: strategy `rolling`, user `2025tm93091`).
After it finishes, **Build with Parameters** → choose `blue-green` → Build. (Optionally one more with `canary`.)

📸 Stage View (all green), console output of *Unit Tests (in container)*, **Test Result**,
**Build Artifacts** (`aceest-fitness-vN.tar.gz`, `sonarqube-report.json`, …), the SonarQube
link/Quality Gate on the build page, and `docker images 2025tm93091/aceest-fitness` / the
Docker Hub tags page showing the new `vN` tags.

## 8. Prove automatic triggering (poll SCM)

Make any small change, e.g. add a line to `README.md`, then:
```powershell
git commit -am "docs: note local Jenkins setup" ; git push
```
Within 5 minutes a new build starts by itself. 📸 build page showing **"Started by an SCM change"**.

## 9. SonarQube results for the submission

http://localhost:9001/dashboard?id=aceest-fitness → 📸 dashboard (Quality Gate, coverage, issues).
```powershell
curl.exe -u "<sonar-token>:" "http://localhost:9001/api/measures/component?component=aceest-fitness&metricKeys=alert_status,bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,ncloc,security_hotspots" -o reports/sonarqube-report.json
git add reports ; git commit -m "docs(reports): add SonarQube report" ; git push
```

---

## If something fails

| Symptom | Fix |
|---|---|
| `Cannot connect to the Docker daemon` in a build | Run `docker exec jenkins docker ps`; if it fails, `cd local ; docker compose down ; docker compose up -d` and make sure Docker Desktop is running |
| Quality Gate stage waits then times out | Webhook missing/wrong in SonarQube (step 3) |
| Quality Gate **FAILED** | open the SonarQube dashboard, read the failing condition; for a demo you can set the default gate on the project to one without the failing condition, then re-run |
| `tool 'sonar-scanner'` not found | Tool name must be exactly `sonar-scanner` (step 6) |
| Deploy stage: `connection refused` / `x509` | kubeconfig server must be `https://192.168.49.2:8443`; re-run step 5 after any `minikube delete` |
| Push fails `unauthorized` | `dockerhub-creds` password must be the access token, not your Google password |
| Jenkins too slow / laptop out of memory | close other apps; `minikube stop` is **not** an option (deploy needs it) — instead tick `SKIP_DEPLOY` for one run |

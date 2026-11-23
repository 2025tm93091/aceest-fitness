# Reports

- `sonarqube-report.json` — SonarQube measures (quality gate, bugs, vulnerabilities, code smells,
  coverage, duplication). Exported with:

  curl -u <token>: "http://localhost:9000/api/measures/component?component=aceest-fitness&metricKeys=alert_status,bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,ncloc,security_hotspots" -o reports/sonarqube-report.json

  Jenkins also archives this file on every build.
- `sonarqube-dashboard.png` — screenshot of the SonarQube project dashboard.

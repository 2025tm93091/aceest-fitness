// ---------------------------------------------------------------------------
// Jenkinsfile — ACEest Fitness & Gym : Assignment 2 CI/CD pipeline
// ---------------------------------------------------------------------------
//  Checkout -> Lint -> Unit Tests (+coverage) -> SonarQube Analysis
//  -> Quality Gate -> Build Image -> Push to Docker Hub
//  -> Deploy to Kubernetes (chosen strategy) -> Smoke Test -> Archive Artifacts
//  Automatic rollback runs if the deploy or smoke test fails.
//
//  One-time Jenkins setup (Manage Jenkins):
//    Plugins     : Pipeline, Git, Docker Pipeline, SonarQube Scanner,
//                  Credentials Binding, JUnit, Timestamper, Workspace Cleanup
//    Credentials : dockerhub-creds  (Username + Docker Hub access token)
//                  kubeconfig       (Secret file - see docs/RUNBOOK.md)
//    System      : SonarQube server named 'sonarqube' (URL + token)
//    Tools       : SonarQube Scanner installation named 'sonar-scanner'
// ---------------------------------------------------------------------------

pipeline {
    agent any

    parameters {
        choice(name: 'DEPLOY_STRATEGY',
               choices: ['rolling', 'blue-green', 'canary', 'ab-testing', 'shadow'],
               description: 'Kubernetes release strategy for this build')
        string(name: 'DOCKERHUB_USER', defaultValue: 'YOUR_DOCKERHUB_USER',
               description: 'Docker Hub account that owns the aceest-fitness repo')
        string(name: 'STABLE_TAG', defaultValue: 'v1',
               description: 'Image tag currently trusted in production')
        booleanParam(name: 'SKIP_DEPLOY', defaultValue: false,
                     description: 'Build/test/push only (no cluster available)')
    }

    // Poll GitHub every 5 minutes; a GitHub webhook also triggers instantly.
    triggers {
        pollSCM('H/5 * * * *')
    }

    environment {
        IMAGE     = "${params.DOCKERHUB_USER}/aceest-fitness"
        IMAGE_TAG = "v${env.BUILD_NUMBER}"
        APP_VER   = "2.0.${env.BUILD_NUMBER}"
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '15'))
        timeout(time: 30, unit: 'MINUTES')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git log -1 --oneline'
            }
        }

        stage('Lint') {
            steps {
                // Same image as production, run as the Jenkins user so files
                // written to the workspace stay owned by Jenkins.
                sh '''
                    docker build -q -t aceest-ci:${BUILD_NUMBER} .
                    docker run --rm -u $(id -u):$(id -g) -e HOME=/tmp \
                      -v "$WORKSPACE:$WORKSPACE" -w "$WORKSPACE" aceest-ci:${BUILD_NUMBER} \
                      flake8 app.py core.py db.py report.py test_app.py --max-line-length=100
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                // Mounted at the same path so coverage.xml paths match for SonarQube.
                sh '''
                    docker run --rm -u $(id -u):$(id -g) -e HOME=/tmp \
                      -e ACEEST_DB_PATH=/tmp/aceest_test.db -e COVERAGE_FILE=/tmp/.coverage \
                      -v "$WORKSPACE:$WORKSPACE" -w "$WORKSPACE" aceest-ci:${BUILD_NUMBER} \
                      pytest -v --junitxml=test-results.xml \
                        --cov=core --cov=db --cov=report --cov=app \
                        --cov-report=term-missing --cov-report=xml:coverage.xml
                '''
            }
            post {
                always { junit 'test-results.xml' }
            }
        }

        stage('SonarQube Analysis') {
            steps {
                script {
                    def scannerHome = tool 'sonar-scanner'
                    withSonarQubeEnv('sonarqube') {
                        sh "${scannerHome}/bin/sonar-scanner -Dsonar.projectVersion=${APP_VER}"
                    }
                }
            }
        }

        stage('Quality Gate') {
            steps {
                // Needs a SonarQube webhook -> http://<jenkins>:8080/sonarqube-webhook/
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
                // Save the SonarQube results as a build artifact (submission deliverable)
                withSonarQubeEnv('sonarqube') {
                    sh '''
                        curl -sf -u "${SONAR_AUTH_TOKEN}:" \
                          "${SONAR_HOST_URL}/api/measures/component?component=aceest-fitness&metricKeys=alert_status,bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,ncloc,security_hotspots" \
                          -o sonarqube-report.json || true
                    '''
                }
            }
        }

        stage('Build Image') {
            steps {
                sh '''
                    docker build --build-arg APP_VERSION=${APP_VER} \
                      -t ${IMAGE}:${IMAGE_TAG} -t ${IMAGE}:latest .
                '''
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DH_USER',
                                                  passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker push ${IMAGE}:${IMAGE_TAG}
                        docker push ${IMAGE}:latest
                        docker logout
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes') {
            when { expression { !params.SKIP_DEPLOY } }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh '''
                        chmod +x scripts/deploy.sh
                        scripts/deploy.sh ${DEPLOY_STRATEGY} ${DOCKERHUB_USER} ${IMAGE_TAG} ${STABLE_TAG}
                    '''
                }
            }
        }

        stage('Smoke Test') {
            when { expression { !params.SKIP_DEPLOY } }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh '''
                        case "${DEPLOY_STRATEGY}" in
                          rolling)    DEP=aceest-rolling ;;
                          blue-green) DEP=aceest-$(kubectl -n aceest get svc aceest-bluegreen -o jsonpath='{.spec.selector.color}') ;;
                          canary)     DEP=aceest-canary ;;
                          ab-testing) DEP=aceest-version-b ;;
                          shadow)     DEP=aceest-shadow ;;
                        esac
                        kubectl -n aceest exec deploy/$DEP -- python -c \
                          "import urllib.request as u; print(u.urlopen('http://localhost:5000/version').read().decode())" \
                          | tee smoke.txt
                        grep -q "${APP_VER}" smoke.txt
                    '''
                }
            }
        }
    }

    post {
        failure {
            script {
                if (!params.SKIP_DEPLOY) {
                    withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                        sh 'scripts/deploy.sh rollback ${DOCKERHUB_USER} ${DEPLOY_STRATEGY} || true'
                    }
                }
            }
            echo "Build ${env.BUILD_NUMBER} failed - rollback attempted"
        }
        success {
            echo "Released ${env.IMAGE}:${env.IMAGE_TAG} with strategy ${params.DEPLOY_STRATEGY}"
        }
        always {
            // Build artifacts: versioned source bundle + manifests + test reports
            sh '''
                tar czf aceest-fitness-${IMAGE_TAG}.tar.gz \
                  app.py core.py db.py report.py requirements.txt Dockerfile k8s scripts \
                  sonar-project.properties || true
            '''
            archiveArtifacts artifacts: 'aceest-fitness-*.tar.gz, coverage.xml, test-results.xml, sonarqube-report.json, smoke.txt',
                             allowEmptyArchive: true, fingerprint: true
            sh 'docker rmi aceest-ci:${BUILD_NUMBER} || true'
        }
    }
}

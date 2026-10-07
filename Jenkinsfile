// ---------------------------------------------------------------------------
// Jenkinsfile — ACEest Fitness CI/CD Pipeline
// ---------------------------------------------------------------------------
// This declarative pipeline:
//   1. Clones the repository from GitHub
//   2. Builds a Docker image
//   3. Runs the pytest suite inside the container
//   4. Runs a flake8 lint check
//   5. (Optional) Deploys the container to port 5000
//
// Triggered by: GitHub webhook (or manual "Build Now")
// ---------------------------------------------------------------------------

pipeline {
    agent any

    environment {
        IMAGE_NAME = 'aceest-fitness'
        IMAGE_TAG  = "build-${env.BUILD_NUMBER}"
        APP_PORT   = '5000'
    }

    options {
        timestamps()
        skipDefaultCheckout(true)          // we checkout manually below
        disableConcurrentBuilds()          // avoid port conflicts
    }

    stages {
        stage('Checkout') {
            steps {
                echo "=== Cloning repository ==="
                git branch: 'main',
                    url: 'https://github.com/2025tm93091/aceest-fitness.git'
            }
        }

        stage('Build Docker Image') {
            steps {
                echo "=== Building Docker image ==="
                sh 'docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .'
            }
        }

        stage('Run Tests in Container') {
            steps {
                echo "=== Running pytest inside the image ==="
                sh '''
                    docker run --rm \
                      -v "$WORKSPACE:/app" \
                      -w /app \
                      ${IMAGE_NAME}:${IMAGE_TAG} \
                      sh -c "pip install pytest pytest-cov && pytest -v --cov=core --cov=db --cov=report --cov=app"
                '''
            }
        }

        stage('Lint') {
            steps {
                echo "=== Running flake8 ==="
                sh '''
                    docker run --rm \
                      -v "$WORKSPACE:/app" \
                      -w /app \
                      ${IMAGE_NAME}:${IMAGE_TAG} \
                      sh -c "pip install flake8 && flake8 app.py core.py db.py report.py --max-line-length=100"
                '''
            }
        }

        stage('Deploy') {
            steps {
                echo "=== Deploying container on port ${APP_PORT} ==="
                sh '''
                    docker stop aceest-app 2>/dev/null || true
                    docker rm aceest-app 2>/dev/null || true
                    docker run -d \
                      --name aceest-app \
                      -p ${APP_PORT}:5000 \
                      ${IMAGE_NAME}:${IMAGE_TAG}
                '''
                sleep 10
                sh '''
                    echo "=== Verifying health endpoint ==="
                    curl -sf http://localhost:${APP_PORT}/health
                '''
            }
        }
    }

    post {
        success {
            echo "✅ Pipeline succeeded — build ${env.BUILD_NUMBER}"
        }
        failure {
            echo "❌ Pipeline failed — build ${env.BUILD_NUMBER}"
        }
        always {
            echo "=== Cleaning old images (keep last 5) ==="
            sh '''
                docker images ${IMAGE_NAME} --format "{{.ID}}" \
                  | tail -n +6 | xargs -r docker rmi -f || true
            '''
        }
    }
}
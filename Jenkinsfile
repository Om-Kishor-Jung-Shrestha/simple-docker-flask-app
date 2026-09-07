pipeline {
    agent any

    parameters {
        string(name: 'ANSIBLE_CONTROLLER_IP', defaultValue: '', description: 'IP address of the Ansible controller')
        string(name: 'ANSIBLE_CONTROLLER_USER', defaultValue: 'ubuntu', description: 'SSH user for Ansible controller')
    }

    environment {
        APP_NAME     = 'simple-docker-flask-app'
        DOCKER_CREDS = credentials('docker-creds')
        IMAGE_TAG    = "${env.BRANCH_NAME ? env.BRANCH_NAME.replaceAll('/', '-') : 'main'}-${env.GIT_COMMIT ? env.GIT_COMMIT.take(7) : 'latest'}"
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out source code...'
                checkout scm
                script {
                    def branch = env.BRANCH_NAME ?: sh(script: 'git rev-parse --abbrev-ref HEAD', returnStdout: true).trim().replaceAll('/', '-')
                    def commit = env.GIT_COMMIT ? env.GIT_COMMIT.take(7) : sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    env.IMAGE_TAG = "${branch}-${commit}"
                }
            }
        }

        stage('Validate Configuration') {
            steps {
                echo 'Validating Docker Compose configuration...'
                sh 'docker compose config'
            }
        }

        stage('Build Docker Image') {
            steps {
                echo "Building Docker image with tag ${IMAGE_TAG}..."
                sh "docker build -t ${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG} -t ${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG} ."
            }
        }

        stage('Test Deployment') {
            steps {
                echo 'Starting application stack with Docker Compose...'
                sh 'WEB_PORT=8081 docker compose up -d'
                sh 'sleep 10'
                sh 'docker compose ps'
                echo 'Running container healthcheck...'
                sh 'docker inspect --format="{{json .State.Health.Status}}" $(docker compose ps -q web) || true'
            }
        }

        stage('Push Docker Image') {
            steps {
                echo 'Logging into Docker Registry...'
                sh 'echo "$DOCKER_CREDS_PSW" | docker login -u "$DOCKER_CREDS_USR" --password-stdin'
                echo "Pushing image ${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG}..."
                sh "docker push ${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG}"
            }
        }
        stage('Deploy via Ansible') {
            steps {
                sshagent(credentials: ['ansible-ssh-key']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no ${params.ANSIBLE_CONTROLLER_USER}@${params.ANSIBLE_CONTROLLER_IP} '
                            cd simple-docker-flask-app-ansible &&
                            ansible-playbook deploy.yml --extra-vars "app_branch=${env.BRANCH_NAME ?: 'main'}"
                        '
                    """
                }
            }
        }
    }

    post {
        always {
            echo 'Cleaning up Docker resources...'
            sh 'docker logout || true'
            sh 'docker compose down -v --remove-orphans || true'
            cleanWs()
        }
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed!'
        }
    }
}
 
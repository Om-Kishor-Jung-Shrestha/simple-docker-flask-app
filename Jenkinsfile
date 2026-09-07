
pipeline {
    agent any

    environment {
        APP_NAME     = 'simple-docker-flask-app'
        DOCKER_CREDS = credentials('dockerhub')
        IMAGE_TAG    = "${env.BRANCH_NAME ? env.BRANCH_NAME.replaceAll('/', '-') : 'main'}-${env.GIT_COMMIT ? env.GIT_COMMIT.take(7) : 'latest'}"
    }

    stages {

        stage('Checkout') {
            steps {
                echo 'Checking out source code...'

                checkout scm

                script {
                    def branch = env.BRANCH_NAME ?:
                        sh(
                            script: 'git rev-parse --abbrev-ref HEAD',
                            returnStdout: true
                        ).trim()

                    branch = branch.replaceAll('/', '-')

                    def commit = env.GIT_COMMIT ?
                        env.GIT_COMMIT.take(7) :
                        sh(
                            script: 'git rev-parse --short HEAD',
                            returnStdout: true
                        ).trim()

                    env.IMAGE_TAG = "${branch}-${commit}"

                    echo "Image tag: ${env.IMAGE_TAG}"
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
                echo "Building Docker image ${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG}..."

                sh """
                    docker build \
                        -t ${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG} \
                        .
                """
            }
        }

        stage('Test Deployment') {
            steps {
                echo 'Starting application stack for testing...'

                sh """
                    APP_IMAGE=${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG} \
                    WEB_PORT=8081 \
                    docker compose up -d
                """

                sh 'sleep 10'

                sh 'docker compose ps'

                echo 'Checking web container health...'

                sh '''
                    docker inspect \
                        --format="{{json .State.Health.Status}}" \
                        $(docker compose ps -q web) || true
                '''
            }
        }

        stage('Push Docker Image') {
            steps {
                echo 'Logging into Docker Hub...'

                sh '''
                    echo "$DOCKER_CREDS_PSW" |
                    docker login \
                        -u "$DOCKER_CREDS_USR" \
                        --password-stdin
                '''

                echo "Pushing ${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG}..."

                sh """
                    docker push \
                        ${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG}
                """
            }
        }

        stage('Deploy via Ansible') {
            steps {
                echo 'Deploying to EC2 #2 using Ansible...'

                sh '''
                    ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook \
                        -i ansible/inventory.ini \
                        ansible/deploy.yml \
                        --extra-vars "docker_image=${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG}"
                '''
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


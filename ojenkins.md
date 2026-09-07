```groovy
pipeline {
    agent any

    environment {
        APP_NAME = 'simple-docker-flask-app'
        DOCKER_CREDS = credentials('dockerhub')
        IMAGE_TAG = "${BUILD_NUMBER}"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Validate') {
            steps {
                sh 'docker compose config'
            }
        }

        stage('Build') {
            steps {
                sh '''
                    docker build \
                        -t ${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG} \
                        .
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                    APP_IMAGE=${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG} \
                    WEB_PORT=8081 \
                    docker compose up -d
                '''

                sh 'sleep 10'

                sh 'docker compose ps'

                sh '''
                    docker inspect \
                        --format="{{json .State.Health.Status}}" \
                        $(docker compose ps -q web)
                '''
            }
        }

        stage('Push') {
            steps {
                sh '''
                    echo "$DOCKER_CREDS_PSW" |
                    docker login \
                        --username "$DOCKER_CREDS_USR" \
                        --password-stdin
                '''

                sh '''
                    docker push \
                        ${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG}
                '''
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    ANSIBLE_CONFIG=ansible/ansible.cfg \
                    ansible-playbook \
                        -i ansible/inventory.ini \
                        ansible/deploy.yml \
                        --extra-vars \
                        "docker_image=${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG}"
                '''
            }
        }
    }

    post {
        always {
            sh 'docker compose down -v --remove-orphans || true'
            sh 'docker logout || true'
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
```

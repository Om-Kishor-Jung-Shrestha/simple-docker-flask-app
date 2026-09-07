Yes. If by **“declarative Jenkins”** you mean **no `script { ... }` blocks and no scripted Groovy logic**, we can simplify the Jenkins pipeline substantially.

The main change is: **don't dynamically manipulate `BRANCH_NAME` and `GIT_COMMIT` using Groovy**. Jenkins already exposes environment variables, and we can use a simple Jenkins build number for the image tag.

Below are the three equivalent CI/CD versions:

1. **Jenkins Declarative Pipeline — no `script`**
2. **GitLab CI/CD**
3. **GitHub Actions**

---

## 1. Jenkins Declarative Pipeline — NO `script`

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
                echo 'Checking out source code...'

                checkout scm

                echo "Git commit: ${GIT_COMMIT}"
                echo "Build number: ${BUILD_NUMBER}"
                echo "Image tag: ${IMAGE_TAG}"
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
                echo 'Deploying to EC2 using Ansible...'

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
```

### What was removed?

Your original had:

```groovy
script {
    def branch = ...
    ...
    env.IMAGE_TAG = "${branch}-${commit}"
}
```

That is **scripted Groovy inside a declarative pipeline**.

The new version has **zero `script {}` blocks**.

The image becomes:

```text
dockerhubusername/simple-docker-flask-app:1
dockerhubusername/simple-docker-flask-app:2
dockerhubusername/simple-docker-flask-app:3
```

where `1`, `2`, `3` are Jenkins `BUILD_NUMBER`s.

This is much easier for a beginner to understand.

---

# 2. GitLab CI/CD equivalent

For GitLab, the file is:

```text
.gitlab-ci.yml
```

A direct equivalent would be:

```yaml
stages:
  - checkout
  - validate
  - build
  - test
  - push
  - deploy


variables:
  APP_NAME: "simple-docker-flask-app"
  IMAGE_TAG: "$CI_PIPELINE_ID"
  IMAGE_NAME: "$DOCKERHUB_USERNAME/$APP_NAME"


checkout:
  stage: checkout
  image: alpine:latest

  script:
    - echo "Checking out source code..."
    - echo "Branch: $CI_COMMIT_BRANCH"
    - echo "Commit: $CI_COMMIT_SHORT_SHA"
    - echo "Pipeline ID: $CI_PIPELINE_ID"


validate:
  stage: validate
  image: docker:cli

  script:
    - echo "Validating Docker Compose configuration..."
    - docker compose config


build:
  stage: build
  image: docker:cli

  script:
    - echo "Building Docker image..."
    - docker build -t "$IMAGE_NAME:$IMAGE_TAG" .


test:
  stage: test
  image: docker:cli

  script:
    - echo "Starting application stack..."
    - APP_IMAGE="$IMAGE_NAME:$IMAGE_TAG" WEB_PORT=8081 docker compose up -d
    - sleep 10
    - docker compose ps


push:
  stage: push
  image: docker:cli

  before_script:
    - echo "$DOCKERHUB_PASSWORD" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin

  script:
    - echo "Pushing Docker image..."
    - docker push "$IMAGE_NAME:$IMAGE_TAG"

  after_script:
    - docker logout || true


deploy:
  stage: deploy
  image: python:3.12

  before_script:
    - pip install ansible
    - apt-get update
    - apt-get install -y openssh-client

  script:
    - echo "Deploying to EC2..."
    - ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook
      -i ansible/inventory.ini
      ansible/deploy.yml
      --extra-vars "docker_image=$IMAGE_NAME:$IMAGE_TAG"
```

You would configure these as **GitLab CI/CD Variables**:

```text
DOCKERHUB_USERNAME
DOCKERHUB_PASSWORD
```

The image might become:

```text
username/simple-docker-flask-app:152
```

where:

```text
CI_PIPELINE_ID = 152
```

---

# 3. GitHub Actions equivalent

For GitHub Actions, create:

```text
.github/workflows/deploy.yml
```

```yaml
name: Build and Deploy


on:
  push:
    branches:
      - main

  pull_request:
    branches:
      - main


env:
  APP_NAME: simple-docker-flask-app
  IMAGE_TAG: ${{ github.run_number }}
  IMAGE_NAME: ${{ secrets.DOCKERHUB_USERNAME }}/simple-docker-flask-app


jobs:

  validate:
    name: Validate Configuration

    runs-on: ubuntu-latest

    steps:
      - name: Checkout source code
        uses: actions/checkout@v4

      - name: Validate Docker Compose
        run: |
          docker compose config


  build:
    name: Build Docker Image

    runs-on: ubuntu-latest

    needs: validate

    steps:
      - name: Checkout source code
        uses: actions/checkout@v4

      - name: Build Docker image
        run: |
          docker build \
            -t $IMAGE_NAME:$IMAGE_TAG \
            .


  test:
    name: Test Deployment

    runs-on: ubuntu-latest

    needs: build

    steps:
      - name: Checkout source code
        uses: actions/checkout@v4

      - name: Build image for testing
        run: |
          docker build \
            -t $IMAGE_NAME:$IMAGE_TAG \
            .

      - name: Start application
        run: |
          APP_IMAGE=$IMAGE_NAME:$IMAGE_TAG \
          WEB_PORT=8081 \
          docker compose up -d

      - name: Wait for application
        run: |
          sleep 10

      - name: Check containers
        run: |
          docker compose ps


  push:
    name: Push Docker Image

    runs-on: ubuntu-latest

    needs: test

    steps:
      - name: Checkout source code
        uses: actions/checkout@v4

      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_PASSWORD }}

      - name: Build Docker image
        run: |
          docker build \
            -t $IMAGE_NAME:$IMAGE_TAG \
            .

      - name: Push Docker image
        run: |
          docker push $IMAGE_NAME:$IMAGE_TAG


  deploy:
    name: Deploy via Ansible

    runs-on: ubuntu-latest

    needs: push

    steps:
      - name: Checkout source code
        uses: actions/checkout@v4

      - name: Install Ansible
        run: |
          python3 -m pip install ansible

      - name: Deploy to EC2
        run: |
          ANSIBLE_CONFIG=ansible/ansible.cfg \
          ansible-playbook \
            -i ansible/inventory.ini \
            ansible/deploy.yml \
            --extra-vars \
            "docker_image=$IMAGE_NAME:$IMAGE_TAG"
```

You'd put these in GitHub repository secrets:

```text
DOCKERHUB_USERNAME
DOCKERHUB_PASSWORD
```

---

# The important difference

Conceptually, all three are doing the same thing:

```text
                   Git Push
                      │
                      ▼
              ┌───────────────┐
              │    Checkout   │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │    Validate   │
              │ Docker Compose│
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │ Docker Build  │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │     Test      │
              │ Docker Compose│
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │ Push to Docker│
              │      Hub      │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │    Ansible    │
              │  Deploy EC2   │
              └───────────────┘
```

The syntax changes:

| Concept         | Jenkins             | GitLab           | GitHub                         |
| --------------- | ------------------- | ---------------- | ------------------------------ |
| Pipeline file   | `Jenkinsfile`       | `.gitlab-ci.yml` | `.github/workflows/deploy.yml` |
| Pipeline stages | `stage()`           | `stages:`        | `jobs:`                        |
| Commands        | `sh`                | `script`         | `run`                          |
| Environment     | `environment`       | `variables`      | `env`                          |
| Secrets         | Jenkins Credentials | CI/CD Variables  | Repository Secrets             |
| Agent           | `agent any`         | Runner           | `runs-on`                      |
| Checkout        | `checkout scm`      | automatic        | `actions/checkout`             |
| Docker          | `sh docker...`      | Docker runner    | Docker available on runner     |
| Deployment      | Ansible             | Ansible          | Ansible                        |

### One important correction

The GitLab/GitHub examples above are **conceptually equivalent**, but for a real pipeline you should usually avoid rebuilding the image multiple times. A better production design is:

```text
Build
  ↓
Test the SAME image
  ↓
Push the SAME image
  ↓
Deploy the SAME image
```

For example:

```text
simple-docker-flask-app:152
             │
       ┌─────┴─────┐
       ↓           ↓
     Test         Push
                   │
                   ↓
                Deploy
```

That guarantees the exact image you tested is the image you deploy.

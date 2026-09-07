# Flask + Redis CI/CD Pipeline: Jenkins, Docker, Ansible, and AWS EC2

**A complete walkthrough of building and debugging a real deployment pipeline**

---

## Introduction

This document walks through a full CI/CD pipeline built for a small Flask + Redis web application. It's not a theoretical exercise — every step here, including the failures, actually happened during the build. The goal was simple to state and harder to execute: push code to GitHub, have Jenkins build and test a Docker image, push that image to Docker Hub, and have Ansible deploy the exact same image to a live server, with zero manual intervention after the `git push`.

The stack:

- **GitHub** — where the source code lives
- **Jenkins** — orchestrates the whole pipeline
- **Docker** — packages the app into a portable image
- **Docker Hub** — stores the built image
- **Ansible** — handles the actual deployment over SSH
- **AWS EC2** — the infrastructure everything runs on
- **Docker Compose** — runs Flask and Redis together on the app server

Two EC2 instances were used, and splitting the responsibilities across them turned out to matter a lot more than it might first appear — most of the debugging in this document traces back to that split.

```text
                         GitHub
                           |
                           | git push
                           v
                    +--------------+
                    |   Jenkins    |
                    |    EC2 #1    |
                    |              |
                    | Docker       |
                    | Ansible      |
                    +--------------+
                           |
                           | SSH
                           | Ansible
                           v
                    +--------------+
                    |    EC2 #2    |
                    | App Server   |
                    |              |
                    | Docker       |
                    | Flask        |
                    | Redis        |
                    +--------------+
                           |
                           | :8080
                           v
                        Browser
```

---

## 1. Why Two Servers Instead of One

It would have been possible to run Jenkins, Docker, Ansible, Flask, and Redis all on a single EC2 instance. That's a common shortcut in tutorials, but it hides an important real-world distinction: the machine that *builds and tests* your software shouldn't be the same machine that *serves it to users*.

So the setup here uses two boxes with very different jobs.

**EC2 #1 — the Jenkins / Ansible controller.** This machine never runs the actual application. Its only job is CI/CD: check out code, build a Docker image, run it briefly to make sure it's healthy, push it to Docker Hub, then hand off to Ansible to deploy it somewhere else.

```text
Elastic IP:       52.5.184.223
Private hostname: ip-172-31-31-87
```

Installed on it:
- Jenkins
- Docker
- Ansible
- An SSH private key, used to reach EC2 #2

**EC2 #2 — the application server.** This is the machine end users actually hit. It runs nothing except Docker, Docker Compose, and the two containers Compose brings up: Flask and Redis.

```text
Elastic IP:       44.216.160.90
Private hostname: ip-172-31-19-118
```

The app is reachable at:

```text
http://44.216.160.90:8080
```

---

## 2. Provisioning the EC2 Instances

Both instances were created as plain Ubuntu boxes from the AWS EC2 console — nothing exotic, no custom AMIs. The only thing that differs between them is what gets installed afterward: Jenkins/Docker/Ansible on #1, Docker/Compose on #2.

### Security groups

Both machines need port 22 open for SSH. EC2 #2 additionally needs port 8080 open so the Flask app is reachable from a browser.

```text
Type:   Custom TCP
Port:   8080
Source: Your IP
```

`0.0.0.0/0` works fine for quick testing, but it means literally anyone on the internet can hit that port. It's worth tightening the source back down to your own IP once you've confirmed things work — leaving it wide open is an easy thing to forget about.

---

## 3. Handling the SSH Key

The EC2 key pair generated during instance creation was named `fedoraos.pem`, kept locally at:

```text
~/Desktop/devopspractice/fedoraos.pem
```

This file is the single most sensitive artifact in the entire project — anyone who has it can SSH into EC2 #2 as the `ubuntu` user. It must never end up in version control. Add this to `.gitignore` immediately, before you do anything else:

```gitignore
*.pem
*.key
```

### Getting the key onto EC2 #1

Since the Jenkins/Ansible controller needs to SSH into EC2 #2 on Jenkins's behalf, the private key has to live on EC2 #1 too. A dedicated credentials directory keeps it out of anyone's home folder:

```bash
sudo mkdir -p /opt/credentials
```

The key was copied to:

```text
/opt/credentials/fedoraos.pem
```

### Locking down permissions

This is where the project ran into its first real snag, and it's worth walking through carefully because the same problem will trip up almost anyone doing this for the first time.

SSH refuses to use a private key if its permissions are too permissive, so the obvious first move is:

```bash
sudo chmod 600 /opt/credentials/fedoraos.pem
```

But there's a second, less obvious wrinkle: **Jenkins doesn't run as your user.** It runs as its own dedicated Linux user, `jenkins`. If the key is still owned by `ubuntu`, Jenkins simply can't read it, no matter how correct the permission bits look. So ownership had to be handed over explicitly:

```bash
sudo chown jenkins:jenkins /opt/credentials/fedoraos.pem
```

Confirming this worked:

```bash
ls -l /opt/credentials/fedoraos.pem
```

```text
-rw------- 1 jenkins jenkins ... fedoraos.pem
```

### The directory permission trap

Here's the part that's easy to miss. Even with the *file* owned by `jenkins` and set to `600`, Jenkins still couldn't read it — because the *parent directory* was created as `ubuntu`-only:

```text
drwx------ ubuntu ubuntu credentials
```

A directory with no execute permission for other users blocks anyone else from traversing into it, regardless of what the files inside look like. Running `namei -l` on the full path made this visible immediately:

```bash
namei -l /opt/credentials/fedoraos.pem
```

The fix was to open up the directory itself, without loosening the file inside it:

```bash
sudo chmod 755 /opt/credentials
```

The end state:

```text
/opt/credentials        755
fedoraos.pem             600
fedoraos.pem owner       jenkins:jenkins
```

In plain terms: Jenkins can walk into the directory, but only Jenkins can actually open and read the key file. Nobody else on the box can touch it.

---

## 4. Verifying SSH Actually Works (as Both Users)

It's tempting to test SSH once and move on, but this setup requires testing it *twice*, as two different users, because a working connection as `ubuntu` doesn't guarantee anything about whether Jenkins can connect.

**First, as yourself (sanity check):**

```bash
sudo ssh -i /opt/credentials/fedoraos.pem ubuntu@44.216.160.90
```

This confirmed basic network reachability and that the key itself was valid.

**Second, as Jenkins specifically** — this is the test that actually matters:

```bash
sudo -u jenkins ssh \
    -i /opt/credentials/fedoraos.pem \
    -o StrictHostKeyChecking=no \
    ubuntu@44.216.160.90 \
    "echo SSH_FROM_JENKINS_SUCCESS"
```

```text
SSH_FROM_JENKINS_SUCCESS
```

Only once this second test passes can you trust that an automated Jenkins pipeline will actually be able to reach the app server. Skipping straight to running the pipeline and hoping for the best is how you end up debugging blind later.

---

## 5. Installing the Tooling on EC2 #1

With permissions sorted, the actual software installs were comparatively uneventful.

**Jenkins:**

```bash
sudo systemctl status jenkins
```

Worth remembering: Jenkins runs as its own `jenkins` user, which is exactly why the permission dance above was necessary in the first place.

**Docker** (Jenkins needs this to build, run, and push images):

```bash
docker --version
docker compose version
```

**Ansible** (the controller needs this to actually deploy):

```bash
ansible --version
```

There is no third machine involved anywhere in this setup — Jenkins runs Ansible directly, and Ansible reaches out over SSH to EC2 #2. That's the entire deployment chain.

```text
Jenkins
   |
   | executes
   v
Ansible
   |
   | SSH
   v
EC2 #2
```

---

## 6. The Application Repository

```text
https://github.com/Om-Kishor-Jung-Shrestha/simple-docker-flask-app.git
```

```bash
cd ~
git clone https://github.com/Om-Kishor-Jung-Shrestha/simple-docker-flask-app.git
```

Structure:

```text
simple-docker-flask-app/
├── ansible/
├── app.py
├── docker-compose.yml
├── Dockerfile
├── Jenkinsfile
├── README.md
├── requirements.txt
├── templates/
└── test/
```

---

## 7. The Ansible Setup

```text
ansible/
├── ansible.cfg
├── deploy.yml
├── inventory.ini
└── roles/
    └── docker_app/
        ├── defaults/main.yml
        ├── handlers/main.yml
        └── tasks/main.yml
```

### Inventory — telling Ansible where to go

`ansible/inventory.ini`:

```ini
[app_servers]
appserver ansible_host=44.216.160.90

[app_servers:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=/opt/credentials/fedoraos.pem
ansible_python_interpreter=/usr/bin/python3
```

This is Ansible's map of the world: one host, called `appserver`, reachable at a specific IP, logged into as `ubuntu`, authenticated with the key sitting at `/opt/credentials/fedoraos.pem`.

### Config — the setting that saved the pipeline later

`ansible/ansible.cfg`:

```ini
[defaults]
inventory = ./inventory.ini
host_key_checking = False
```

That single line, `host_key_checking = False`, turns out to matter a great deal — see the deployment failure in Section 10 below. Without it, Ansible stops and waits for interactive confirmation the first time it connects to a new host, which is fine for a human at a terminal and fatal for an automated pipeline.

### Confirming Ansible can actually reach the target

```bash
cd ~/simple-docker-flask-app/ansible
ansible app_servers -m ping
```

```text
appserver | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

### The playbook

`ansible/deploy.yml`:

```yaml
---
- name: Provision Docker and deploy simple-docker-flask-app via Docker Compose
  hosts: app_servers
  become: true

  roles:
    - docker_app
```

All the real work lives inside the `docker_app` role.

### Role defaults

`ansible/roles/docker_app/defaults/main.yml`:

```yaml
---
app_repo: "https://github.com/Om-Kishor-Jung-Shrestha/simple-docker-flask-app.git"
app_branch: "main"
app_dir: "/opt/simple-docker-flask-app"

docker_image: ""
```

Note that `docker_image` starts empty. That's deliberate — the role doesn't know what image tag to deploy on its own. Jenkins fills that in at runtime, which is what lets one generic role deploy any build without editing YAML by hand.

Example of what Jenkins passes in:

```text
lzero0/simple-docker-flask-app:main-8ed0423
```

### What the role actually does

Roughly, in order: install prerequisite packages, add Docker's official GPG key and APT repo, install Docker Engine and the Compose plugin, make sure the Docker service is running and enabled, add the `ubuntu` user to the `docker` group, clone or update the application repo, and finally deploy the image:

```yaml
- name: Deploy Docker image
  shell: |
    cd {{ app_dir }}
    export APP_IMAGE="{{ docker_image }}"
    docker compose pull web
    docker compose up -d
  args:
    executable: /bin/bash
  when: docker_image | length > 0
```

That `when` guard matters: if Jenkins somehow forgot to pass a `docker_image`, the role skips the deploy step instead of trying to bring up a container with no image specified.

---

## 8. Docker Compose: Flask and Redis Together

The application is two services: `web` (Flask) and `redis`.

```yaml
services:
  web:
    image: ${APP_IMAGE:-simple-docker-flask-app:local}
    ports:
      - "${WEB_PORT:-8080}:5000"
    environment:
      - APP_NAME=${APP_NAME}
      - APP_COLOR=${APP_COLOR}
      - APP_ENV=${APP_ENV}
      - REDIS_HOST=redis
      - REDIS_PORT=${REDIS_PORT:-6379}
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - study-net

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - study-net

networks:
  study-net:

volumes:
  redis-data:
```

A couple of details worth calling out:

- **`depends_on` with `condition: service_healthy`** means Flask won't even start until Redis has passed its own health check, not just "started." That's a meaningfully stronger guarantee than plain `depends_on`.
- **Port mapping** takes whatever's on the container's internal port 5000 (where Flask listens) and exposes it externally on 8080 by default. So the traffic path is: browser hits `:8080` on the host → Docker forwards it to `:5000` inside the container → Flask handles it.

```text
Browser
   |
   | :8080
   v
EC2 #2
   |
   | Docker
   v
Flask container :5000
```

### Why `image:` instead of `build: .`

This is a small line in the Compose file that encodes a fairly important CI/CD principle. The file says:

```yaml
image: ${APP_IMAGE:-simple-docker-flask-app:local}
```

not

```yaml
build: .
```

If the app server rebuilt the image itself from source every time it deployed, you'd lose the guarantee that what's running in production is *exactly* what Jenkins built and tested. Small differences in build environment, cached layers, or dependency resolution could sneak in. Instead, the image is built exactly once, by Jenkins, tested, pushed to Docker Hub, and then EC2 #2 just pulls that specific tagged image and runs it, unchanged.

```text
Jenkins builds  →  Jenkins tests  →  Docker Hub stores  →  EC2 #2 pulls and runs
```

This is the classic "build once, deploy the same artifact everywhere" pattern, and it's the reason the image tag includes a Git commit hash — so you can always trace a running container back to the exact commit it came from.

---

## 9. Docker Hub

Repository:

```text
lzero0/simple-docker-flask-app
```

Jenkins authenticates using a credential stored inside Jenkins itself — never hard-coded into the Jenkinsfile:

```text
Credential ID: dockerhub
```

---

## 10. The Jenkins Pipeline

### Environment and image tagging

```groovy
environment {
    APP_NAME     = 'simple-docker-flask-app'
    DOCKER_CREDS = credentials('dockerhub')
    IMAGE_TAG    = "${env.BRANCH_NAME ? env.BRANCH_NAME.replaceAll('/', '-') : 'main'}-${env.GIT_COMMIT ? env.GIT_COMMIT.take(7) : 'latest'}"
}
```

Every image gets tagged with its branch name plus the short Git commit hash — e.g. `main-8ed0423`. This is what gives you traceability: looking at a running container tells you exactly which commit produced it.

### Pipeline stages

```text
Checkout
   |
   v
Validate Configuration
   |
   v
Build Docker Image
   |
   v
Test Deployment
   |
   v
Push Docker Image
   |
   v
Deploy via Ansible
```

**Checkout** — pulls source from GitHub and determines branch and commit for the tag.

**Validate Configuration** — runs `docker compose config` to catch obvious mistakes before anything gets built. During this project, warnings appeared for `APP_COLOR` and `APP_ENV` not being set — non-fatal, and the pipeline continued.

**Build Docker Image:**

```bash
docker build -t lzero0/simple-docker-flask-app:main-8ed0423 .
```

**Test Deployment** — this is the step that actually earns the "CI" in CI/CD. Rather than trusting that a built image works, Jenkins spins it up for real, on a *different* port than production so it doesn't collide with anything:

```bash
APP_IMAGE=lzero0/simple-docker-flask-app:main-8ed0423 \
WEB_PORT=8081 \
docker compose up -d
```

After a short `sleep 10` to let containers settle, Jenkins checks:

```bash
docker compose ps
```

The web container reported `healthy` — meaning the image is proven to actually work *before* it ever gets pushed anywhere.

**Push Docker Image:**

```bash
echo "$DOCKER_CREDS_PSW" | docker login -u "$DOCKER_CREDS_USR" --password-stdin
docker push lzero0/simple-docker-flask-app:main-8ed0423
```

**Deploy via Ansible:**

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook \
    -i ansible/inventory.ini \
    ansible/deploy.yml \
    --extra-vars "docker_image=${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG}"
```

That leading `ANSIBLE_CONFIG=ansible/ansible.cfg` looks like a minor flourish but it's the fix for a real failure — explained next.

---

## 11. What Actually Went Wrong (and How Each Was Fixed)

Nothing in this pipeline worked on the first try. That's normal, and it's more useful to document the failures than to pretend the happy path was obvious from the start.

### Failure 1 — Host key verification failed

The very first automated Jenkins deployment failed outright with:

```text
Host key verification failed.
```

Oddly, running the exact same Ansible command by hand worked fine. The difference turned out to be *where* each was running from. Jenkins executes the pipeline from:

```text
/var/lib/jenkins/workspace/jenkins
```

and Ansible doesn't automatically go looking for a config file inside a subdirectory like `ansible/` unless it's told to. So the `host_key_checking = False` setting in `ansible.cfg` simply wasn't being picked up when Jenkins ran the command. The fix was to point Ansible at the config file explicitly:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ...
```

### Failure 2 — PEM permission denied

Next:

```text
no such identity: /opt/credentials/fedoraos.pem: Permission denied
```

This was the ownership issue from Section 3 — the key existed but Jenkins couldn't read it yet. Fixed with:

```bash
sudo chown jenkins:jenkins /opt/credentials/fedoraos.pem
sudo chmod 600 /opt/credentials/fedoraos.pem
```

### Failure 3 — Still permission denied, even after fixing the file

This one was sneakier. Even with the file correctly owned and permissioned, Jenkins *still* couldn't read it. Running `namei -l` on the full path exposed the real problem:

```text
drwx------ ubuntu ubuntu credentials
-rw------- jenkins jenkins fedoraos.pem
```

The file itself was fine. The *directory it lived in* wasn't traversable by anyone except `ubuntu`. Fixed with:

```bash
sudo chmod 755 /opt/credentials
```

After that, the Jenkins-as-user SSH test (Section 4) finally succeeded:

```text
SSH_FROM_JENKINS_SUCCESS
```

### Two smaller operational issues

**Jenkins stuck waiting for an executor.** The Jenkins server's `/tmp` was a small tmpfs mount, and it was too small for the pipeline to schedule properly. Temporary fix:

```bash
sudo mount -o remount,size=2G /tmp
```

**Jenkinsfile compilation error.** The Jenkinsfile accidentally had Markdown code-fence syntax left in it (a stray ` ```groovy ` line) — leftover from copy-pasting out of documentation. A Jenkinsfile has to start directly with:

```groovy
pipeline {
```

with no Markdown formatting anywhere in the actual file.

---

## 12. Confirming the Deployment Manually

Before trusting Jenkins to run the whole thing end to end, the Ansible deployment was run manually once to confirm the playbook itself was sound, independent of any Jenkins quirks:

```bash
ansible-playbook \
    -i inventory.ini \
    deploy.yml \
    --extra-vars "docker_image=lzero0/simple-docker-flask-app:main-3dc70b0" \
    -e 'ansible_host_key_checking=false'
```

```text
PLAY RECAP
appserver : ok=9 changed=6 unreachable=0 failed=0 skipped=0 rescued=0 ignored=0
```

Nine tasks succeeded, six actually changed something on the target — no failures, nothing unreachable. That's the signal the role itself was correct, which made it much easier to isolate the later Jenkins-specific issues as *environment* problems rather than *logic* problems.

---

## 13. The Pipeline, Finally Green

```text
Checkout                         SUCCESS
Validate Configuration           SUCCESS
Build Docker Image               SUCCESS
Test Deployment                  SUCCESS
Push Docker Image                SUCCESS
Deploy via Ansible               SUCCESS
Cleanup                          SUCCESS

Pipeline completed successfully!
Finished: SUCCESS
```

---

## 14. Verifying the Live Application

SSH into EC2 #2 and check what's actually running:

```bash
ssh -i /opt/credentials/fedoraos.pem ubuntu@44.216.160.90
cd /opt/simple-docker-flask-app
sudo docker compose ps
```

```text
simple-docker-flask-app-redis-1   redis:7-alpine                              Up (healthy)
simple-docker-flask-app-web-1     lzero0/simple-docker-flask-app:main-8ed0423 Up (healthy)   0.0.0.0:8080->5000/tcp
```

Both services healthy, and the port mapping confirms external traffic on 8080 reaches the Flask container's internal 5000.

The app is live at:

```text
http://44.216.160.90:8080
```

### If it works locally but not in a browser

Try this from EC2 #2 itself first:

```bash
curl http://localhost:8080
```

If that returns a response but the browser still can't connect, the application is fine — it's almost always the EC2 Security Group blocking inbound traffic on 8080 from your IP. Double-check that rule before looking anywhere else.

### A note on the two different ports

It's easy to get confused between two ports that show up during this process:

```text
Jenkins's temporary test container:   EC2 #1, port 8081
The real, deployed application:       EC2 #2, port 8080
```

Port 8081 only ever exists briefly, during the Test Deployment stage, on the *build* server — it's not something end users ever touch. The actual production traffic goes to 8080 on the *app* server. Conflating the two while debugging is a common source of confusion.

---

## 15. Security Notes

The following should never, under any circumstances, end up committed to the repository:

```text
*.pem / *.key           — private keys
.env                     — environment secrets
AWS credentials
Docker Hub tokens
API keys
Passwords
```

A reasonably complete `.gitignore` for this kind of project:

```gitignore
.env
.env.*
!.env.example

*.pem
*.key
*.p12
*.pfx

__pycache__/
*.py[cod]

.venv/
venv/
env/

node_modules/

npm-debug.log*
yarn-debug.log*
pnpm-debug.log*

.DS_Store

.vscode/
.idea/

*.log
logs/

.terraform/
*.tfstate
*.tfstate.*
.terraform.lock.hcl
```

Secrets that Jenkins needs — like the Docker Hub token — belong in **Jenkins Credentials**, referenced from the Jenkinsfile rather than written into it:

```groovy
DOCKER_CREDS = credentials('dockerhub')
```

The SSH private key stays on disk on the controller only, owned by `jenkins`, permissioned `600`, at `/opt/credentials/fedoraos.pem`.

---

## 16. The Complete Flow, Start to Finish

```text
1.  Developer writes code
2.  git push
3.  GitHub receives it
4.  Jenkins detects the change and starts a build
5.  Checkout source
6.  Validate Docker Compose config
7.  Build Docker image
8.  Spin up Flask + Redis as a real test, on a scratch port
9.  Verify both containers report healthy
10. Push the proven image to Docker Hub
11. Jenkins hands off to Ansible
12. Ansible SSHs into EC2 #2 as jenkins, using the stored key
13. EC2 #2 pulls that exact image — nothing is rebuilt on the app server
14. Docker Compose starts (or updates) the Flask + Redis containers
15. Health checks pass
16. The application is live on :8080
```

---

## 17. Final Verification Checklist

```text
[✓] Two EC2 instances created
[✓] EC2 #1 configured as Jenkins server
[✓] EC2 #1 configured as Ansible controller
[✓] Docker installed on EC2 #1
[✓] Ansible installed on EC2 #1
[✓] EC2 #2 configured as application server
[✓] Docker installed on EC2 #2
[✓] SSH key copied to EC2 #1
[✓] PEM permissions secured
[✓] Jenkins can access PEM
[✓] EC2 #1 can SSH to EC2 #2
[✓] Jenkins user can SSH to EC2 #2
[✓] Ansible ping works
[✓] GitHub repository connected
[✓] Docker Hub repository created
[✓] Jenkins Docker credential configured
[✓] Docker Compose validated
[✓] Docker image built
[✓] Flask container tested
[✓] Redis container tested
[✓] Health checks passed
[✓] Docker image pushed
[✓] Ansible deployment succeeded
[✓] Flask running on EC2 #2
[✓] Redis running on EC2 #2
[✓] Flask container healthy
[✓] Redis container healthy
[✓] Port 8080 exposed
[✓] Jenkins pipeline finished SUCCESS
```

---

## 18. Closing Thoughts

Almost none of the difficulty in this project came from Flask, Redis, or Docker Compose themselves — those parts worked more or less as documented. Nearly every real obstacle was about **permissions and identity**: which Linux user Jenkins actually runs as, whether that user could read a file, and whether it could even get *into* the directory the file lived in. That's a pattern worth remembering for any future pipeline work — when something works fine manually but fails under automation, the first question should almost always be "which user is actually running this, and can that user see what it needs to see?"

The other lesson worth keeping is the "build once, deploy the same artifact everywhere" principle baked into the Compose file's use of `image:` over `build:`. It's a small YAML choice, but it's the difference between *hoping* your production environment matches what you tested and *knowing* it does, because it's the literal same image, identified by the same Git commit.

The final, working system:

```text
GitHub → Jenkins → Docker Build → Docker Test → Docker Hub → Ansible → EC2 #2 → Docker Compose → Flask + Redis → Browser
```

Live at:

```text
http://44.216.160.90:8080
```
----

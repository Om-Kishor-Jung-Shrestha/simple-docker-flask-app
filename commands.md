descirbe the command run here:
Yes — you mean **the entire DevOps lab command history**, not just the final Ansible deployment: AWS CLI installation/configuration → AWS EC2 → SSH → Jenkins → Docker → Ansible → GitHub → Docker Hub → CI/CD → troubleshooting → deployment.

I don't have a verbatim terminal history for every earlier command, so I shouldn't pretend these are literally every command ever typed. But below is the **complete command sequence represented by our conversation, including the setup commands we discussed/used**.

# Complete AWS → Jenkins → Docker → Ansible CI/CD Command Sheet

## 1. Local machine — install AWS CLI

### Check whether AWS CLI exists

```bash
aws --version
```

### Ubuntu/Debian installation

```bash
sudo apt update
sudo apt install -y unzip curl
```

Download AWS CLI:

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
```

Extract:

```bash
unzip awscliv2.zip
```

Install:

```bash
sudo ./aws/install
```

Verify:

```bash
aws --version
```

Clean up:

```bash
rm -rf aws awscliv2.zip
```

---

# 2. Configure AWS CLI

```bash
aws configure
```

Enter:

```text
AWS Access Key ID:
AWS Secret Access Key:
Default region name:
Default output format:
```

For example:

```text
ap-south-1
json
```

Check configuration:

```bash
aws configure list
```

Test authentication:

```bash
aws sts get-caller-identity
```

Expected structure:

```json
{
    "UserId": "...",
    "Account": "...",
    "Arn": "..."
}
```

---

# 3. Check AWS regions

```bash
aws ec2 describe-regions \
    --query "Regions[].RegionName" \
    --output table
```

Set a default region:

```bash
aws configure set region ap-south-1
```

Verify:

```bash
aws configure get region
```

---

# 4. AWS — inspect EC2 instances

List instances:

```bash
aws ec2 describe-instances
```

Only running instances:

```bash
aws ec2 describe-instances \
    --filters Name=instance-state-name,Values=running
```

More readable:

```bash
aws ec2 describe-instances \
    --query 'Reservations[].Instances[].[
        InstanceId,
        State.Name,
        InstanceType,
        PublicIpAddress,
        PrivateIpAddress
    ]' \
    --output table
```

---

# 5. AWS — create/check key pairs

List key pairs:

```bash
aws ec2 describe-key-pairs \
    --query 'KeyPairs[].KeyName' \
    --output table
```

If creating a new key pair:

```bash
aws ec2 create-key-pair \
    --key-name devops-key \
    --query 'KeyMaterial' \
    --output text > devops-key.pem
```

Secure it:

```bash
chmod 400 devops-key.pem
```

In our actual setup the existing key was:

```text
fedoraos.pem
```

---

# 6. AWS — inspect security groups

```bash
aws ec2 describe-security-groups \
    --output table
```

List IDs/names:

```bash
aws ec2 describe-security-groups \
    --query 'SecurityGroups[].[
        GroupId,
        GroupName,
        VpcId
    ]' \
    --output table
```

---

# 7. AWS — open SSH port

Example:

```bash
aws ec2 authorize-security-group-ingress \
    --group-id sg-XXXXXXXX \
    --protocol tcp \
    --port 22 \
    --cidr YOUR_IP/32
```

For temporary testing from anywhere:

```bash
aws ec2 authorize-security-group-ingress \
    --group-id sg-XXXXXXXX \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0
```

---

# 8. AWS — open application port 8080

```bash
aws ec2 authorize-security-group-ingress \
    --group-id sg-XXXXXXXX \
    --protocol tcp \
    --port 8080 \
    --cidr YOUR_IP/32
```

Temporary testing:

```bash
aws ec2 authorize-security-group-ingress \
    --group-id sg-XXXXXXXX \
    --protocol tcp \
    --port 8080 \
    --cidr 0.0.0.0/0
```

---

# 9. SSH into EC2 #1

Our Jenkins EC2:

```text
52.5.184.223
```

From the local machine:

```bash
chmod 400 ~/Desktop/devopspractice/fedoraos.pem
```

SSH:

```bash
ssh \
    -i ~/Desktop/devopspractice/fedoraos.pem \
    ubuntu@52.5.184.223
```

---

# 10. Update EC2 #1

```bash
sudo apt update
```

```bash
sudo apt upgrade -y
```

Install common utilities:

```bash
sudo apt install -y \
    curl \
    wget \
    git \
    unzip \
    vim \
    ca-certificates \
    gnupg \
    lsb-release
```

---

# 11. Install Java for Jenkins

Check Java:

```bash
java -version
```

Install OpenJDK:

```bash
sudo apt install -y openjdk-21-jdk
```

Verify:

```bash
java -version
```

Check:

```bash
javac -version
```

---

# 12. Install Jenkins repository

Add Jenkins key:

```bash
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key |
    sudo tee \
    /usr/share/keyrings/jenkins-keyring.asc \
    > /dev/null
```

Add repository:

```bash
echo deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] \
    https://pkg.jenkins.io/debian-stable binary/ |
    sudo tee \
    /etc/apt/sources.list.d/jenkins.list \
    > /dev/null
```

Update:

```bash
sudo apt update
```

Install:

```bash
sudo apt install -y jenkins
```

---

# 13. Start Jenkins

```bash
sudo systemctl start jenkins
```

Enable at boot:

```bash
sudo systemctl enable jenkins
```

Check:

```bash
sudo systemctl status jenkins
```

---

# 14. Get Jenkins initial password

```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

Jenkins normally runs on:

```text
http://52.5.184.223:8080
```

If Jenkins itself is using port 8080, remember that the application later uses port 8080 on **EC2 #2**, not EC2 #1.

---

# 15. Check Jenkins user

```bash
id jenkins
```

```bash
getent passwd jenkins
```

---

# 16. Install Docker on EC2 #1

Remove conflicting packages if necessary:

```bash
sudo apt remove -y \
    docker.io \
    docker-doc \
    docker-compose \
    podman-docker \
    containerd \
    runc
```

Install prerequisites:

```bash
sudo apt update
```

```bash
sudo apt install -y \
    ca-certificates \
    curl \
    gnupg
```

Create keyring directory:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
```

Add Docker GPG key:

```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg |
    sudo gpg --dearmor \
    -o /etc/apt/keyrings/docker.gpg
```

Set permissions:

```bash
sudo chmod a+r /etc/apt/keyrings/docker.gpg
```

Add Docker repository:

```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

Update:

```bash
sudo apt update
```

Install Docker:

```bash
sudo apt install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin
```

---

# 17. Start Docker

```bash
sudo systemctl start docker
```

```bash
sudo systemctl enable docker
```

Check:

```bash
sudo systemctl status docker
```

Check version:

```bash
docker --version
```

Check Compose:

```bash
docker compose version
```

---

# 18. Allow Jenkins to use Docker

This is important.

```bash
sudo usermod -aG docker jenkins
```

Verify:

```bash
groups jenkins
```

Restart Jenkins:

```bash
sudo systemctl restart jenkins
```

Test:

```bash
sudo -u jenkins docker ps
```

---

# 19. Install Ansible on EC2 #1

```bash
sudo apt update
```

```bash
sudo apt install -y ansible
```

Check:

```bash
ansible --version
```

---

# 20. Create credentials directory

```bash
sudo mkdir -p /opt/credentials
```

---

# 21. Copy PEM from local machine to EC2 #1

From your **local computer**:

```bash
scp \
    -i ~/Desktop/devopspractice/fedoraos.pem \
    ~/Desktop/devopspractice/fedoraos.pem \
    ubuntu@52.5.184.223:/tmp/fedoraos.pem
```

Then on EC2 #1:

```bash
sudo mv \
    /tmp/fedoraos.pem \
    /opt/credentials/fedoraos.pem
```

---

# 22. Set PEM permissions

```bash
sudo chown jenkins:jenkins \
    /opt/credentials/fedoraos.pem
```

```bash
sudo chmod 600 \
    /opt/credentials/fedoraos.pem
```

Fix parent directory:

```bash
sudo chmod 755 /opt/credentials
```

Check:

```bash
ls -ld /opt/credentials
```

```bash
ls -l /opt/credentials/fedoraos.pem
```

Check complete path:

```bash
namei -l /opt/credentials/fedoraos.pem
```

---

# 23. Test SSH EC2 #1 → EC2 #2

EC2 #2:

```text
44.216.160.90
```

From EC2 #1:

```bash
sudo ssh \
    -i /opt/credentials/fedoraos.pem \
    ubuntu@44.216.160.90
```

Exit:

```bash
exit
```

---

# 24. Test SSH as Jenkins

```bash
sudo -u jenkins ssh \
    -i /opt/credentials/fedoraos.pem \
    -o StrictHostKeyChecking=no \
    ubuntu@44.216.160.90 \
    "echo SSH_FROM_JENKINS_SUCCESS"
```

Expected:

```text
SSH_FROM_JENKINS_SUCCESS
```

---

# 25. Clone GitHub repository

On EC2 #1:

```bash
cd ~
```

```bash
git clone \
    https://github.com/Om-Kishor-Jung-Shrestha/simple-docker-flask-app.git
```

Enter directory:

```bash
cd ~/simple-docker-flask-app
```

Check:

```bash
ls
```

Git status:

```bash
git status
```

---

# 26. Check project

```bash
find . -maxdepth 3 -type f | sort
```

Expected major files:

```text
app.py
Dockerfile
docker-compose.yml
Jenkinsfile
requirements.txt
ansible/
```

---

# 27. Configure Ansible

```bash
cd ~/simple-docker-flask-app/ansible
```

Check:

```bash
ls
```

Test inventory:

```bash
ansible-inventory \
    -i inventory.ini \
    --list
```

---

# 28. Test Ansible

```bash
ansible app_servers -m ping
```

Expected:

```text
appserver | SUCCESS
```

---

# 29. Manual Ansible deployment

```bash
ansible-playbook \
    -i inventory.ini \
    deploy.yml \
    --extra-vars \
    "docker_image=lzero0/simple-docker-flask-app:main-3dc70b0"
```

The successful recap was:

```text
appserver : ok=9 changed=6 unreachable=0 failed=0 skipped=0 rescued=0 ignored=0
```

---

# 30. SSH into EC2 #2

```bash
sudo ssh \
    -i /opt/credentials/fedoraos.pem \
    ubuntu@44.216.160.90
```

---

# 31. EC2 #2 — update system

```bash
sudo apt update
```

```bash
sudo apt upgrade -y
```

Install basic packages:

```bash
sudo apt install -y \
    curl \
    git \
    ca-certificates \
    gnupg
```

---

# 32. EC2 #2 — Docker

Check:

```bash
docker --version
```

```bash
docker compose version
```

Check service:

```bash
sudo systemctl status docker
```

Start:

```bash
sudo systemctl start docker
```

Enable:

```bash
sudo systemctl enable docker
```

---

# 33. EC2 #2 — application directory

After Ansible:

```bash
cd /opt/simple-docker-flask-app
```

Check:

```bash
ls
```

---

# 34. Docker Compose validation

```bash
sudo docker compose config
```

---

# 35. Pull application image

```bash
sudo docker compose pull
```

---

# 36. Start application

```bash
sudo docker compose up -d
```

---

# 37. Check containers

```bash
sudo docker compose ps
```

Also:

```bash
sudo docker ps
```

All containers, including stopped:

```bash
sudo docker ps -a
```

---

# 38. Check logs

Flask:

```bash
sudo docker compose logs web
```

Redis:

```bash
sudo docker compose logs redis
```

Everything:

```bash
sudo docker compose logs
```

Follow:

```bash
sudo docker compose logs -f
```

---

# 39. Test Flask

```bash
curl http://localhost:8080
```

---

# 40. Test Redis

```bash
sudo docker exec \
    simple-docker-flask-app-redis-1 \
    redis-cli ping
```

Expected:

```text
PONG
```

---

# 41. Docker images

```bash
sudo docker images
```

Search application image:

```bash
sudo docker images | grep simple-docker-flask-app
```

---

# 42. Stop Compose

```bash
sudo docker compose down
```

Start:

```bash
sudo docker compose up -d
```

Pull + start:

```bash
sudo docker compose pull
sudo docker compose up -d
```

---

# 43. Local Git commands

Check:

```bash
git status
```

Add:

```bash
git add .
```

Commit:

```bash
git commit -m "Configure Docker CI/CD with Ansible deployment"
```

Push:

```bash
git push origin main
```

Later Jenkinsfile fix:

```bash
git add Jenkinsfile
```

```bash
git commit -m "Fix Ansible config loading in Jenkins"
```

```bash
git push origin main
```

---

# 44. Git history

```bash
git log --oneline
```

Latest commit:

```bash
git log -1
```

Current branch:

```bash
git branch --show-current
```

Remote:

```bash
git remote -v
```

---

# 45. Docker build

The Jenkins build effectively ran:

```bash
docker build \
    -t lzero0/simple-docker-flask-app:main-8ed0423 \
    .
```

Check image:

```bash
docker images | grep simple-docker-flask-app
```

---

# 46. Run test deployment

```bash
APP_IMAGE=lzero0/simple-docker-flask-app:main-8ed0423 \
WEB_PORT=8081 \
docker compose up -d
```

Wait:

```bash
sleep 10
```

Check:

```bash
docker compose ps
```

Check health:

```bash
docker inspect \
    --format="{{json .State.Health.Status}}" \
    $(docker compose ps -q web) || true
```

---

# 47. Docker Hub login

Interactive:

```bash
docker login
```

Jenkins used the non-interactive form:

```bash
echo "$DOCKER_CREDS_PSW" |
docker login \
    -u "$DOCKER_CREDS_USR" \
    --password-stdin
```

---

# 48. Push Docker image

```bash
docker push \
    lzero0/simple-docker-flask-app:main-8ed0423
```

Image:

```text
lzero0/simple-docker-flask-app:main-8ed0423
```

Digest from the successful push:

```text
sha256:98bd050ccb2f12b75b92c0600752566621ce6140c427050b7f2c9e4189a4d837
```

---

# 49. Ansible deployment from Jenkins

The final command:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg \
ansible-playbook \
    -i ansible/inventory.ini \
    ansible/deploy.yml \
    --extra-vars \
    "docker_image=${DOCKER_CREDS_USR}/${APP_NAME}:${IMAGE_TAG}"
```

For the successful build:

```text
lzero0/simple-docker-flask-app:main-8ed0423
```

---

# 50. Jenkins cleanup

```bash
docker logout || true
```

```bash
docker compose down -v --remove-orphans || true
```

---

# 51. Jenkins `/tmp` troubleshooting

Check:

```bash
df -h /tmp
```

Check root filesystem:

```bash
df -h /
```

Temporary increase:

```bash
sudo mount -o remount,size=2G /tmp
```

Verify:

```bash
df -h /tmp
```

---

# 52. Jenkins permission troubleshooting

Check:

```bash
id jenkins
```

Check directory:

```bash
ls -ld /opt/credentials
```

Check key:

```bash
ls -l /opt/credentials/fedoraos.pem
```

Test readability:

```bash
sudo -u jenkins \
    test -r /opt/credentials/fedoraos.pem \
    && echo "KEY_READABLE"
```

---

# 53. Diagnose PEM path permissions

```bash
namei -l /opt/credentials/fedoraos.pem
```

The important final state:

```text
/opt/credentials       755
fedoraos.pem            600
owner                   jenkins:jenkins
```

---

# 54. Check Jenkins logs

If Jenkins isn't starting:

```bash
sudo journalctl -u jenkins
```

Recent logs:

```bash
sudo journalctl -u jenkins -n 100
```

Follow:

```bash
sudo journalctl -u jenkins -f
```

---

# 55. Check Docker logs

```bash
sudo journalctl -u docker -n 100
```

Follow:

```bash
sudo journalctl -u docker -f
```

---

# 56. Check listening ports

On EC2:

```bash
sudo ss -tulpn
```

Specific port:

```bash
sudo ss -tulpn | grep 8080
```

Jenkins:

```bash
sudo ss -tulpn | grep 8080
```

This is useful because Jenkins and your application should not try to use the same port on the same EC2.

---

# 57. Check EC2 networking

```bash
ip addr
```

```bash
ip route
```

Public IP:

```bash
curl ifconfig.me
```

---

# 58. Test EC2 #2 from EC2 #1

```bash
curl http://44.216.160.90:8080
```

Test SSH:

```bash
ssh \
    -i /opt/credentials/fedoraos.pem \
    ubuntu@44.216.160.90
```

---

# 59. Test application from local computer

```bash
curl http://44.216.160.90:8080
```

Or browser:

```text
http://44.216.160.90:8080
```

---

# 60. Final verification commands

### EC2 #1

```bash
sudo systemctl status jenkins
```

```bash
docker --version
```

```bash
docker compose version
```

```bash
ansible --version
```

```bash
sudo -u jenkins docker ps
```

```bash
sudo -u jenkins ssh \
    -i /opt/credentials/fedoraos.pem \
    -o StrictHostKeyChecking=no \
    ubuntu@44.216.160.90 \
    "echo SSH_FROM_JENKINS_SUCCESS"
```

### EC2 #2

```bash
cd /opt/simple-docker-flask-app
```

```bash
sudo docker compose ps
```

```bash
sudo docker ps
```

```bash
curl http://localhost:8080
```

```bash
sudo docker compose logs --tail=100
```

### Local

```bash
aws sts get-caller-identity
```

```bash
ssh -i ~/Desktop/devopspractice/fedoraos.pem ubuntu@52.5.184.223
```

---

# 61. The whole thing in one flow

```text
LOCAL MACHINE
│
├── aws --version
├── aws configure
├── aws sts get-caller-identity
├── aws ec2 describe-instances
├── chmod 400 fedoraos.pem
├── ssh -i fedoraos.pem ubuntu@52.5.184.223
│
▼
EC2 #1
│
├── apt update
├── apt upgrade
├── install Java
├── install Jenkins
├── systemctl enable --now jenkins
│
├── install Docker
├── systemctl enable --now docker
├── usermod -aG docker jenkins
│
├── install Ansible
│
├── /opt/credentials/fedoraos.pem
├── chown jenkins:jenkins fedoraos.pem
├── chmod 600 fedoraos.pem
├── chmod 755 /opt/credentials
│
├── SSH → EC2 #2
│
├── git clone GitHub
├── ansible app_servers -m ping
│
├── Jenkins
│   ├── docker compose config
│   ├── docker build
│   ├── docker compose up
│   ├── docker compose ps
│   ├── docker push
│   └── ansible-playbook
│
▼
EC2 #2
│
├── Docker
├── Docker Compose
├── git repository
│
├── docker compose pull
├── docker compose up -d
├── docker compose ps
├── docker compose logs
│
├── Flask :5000
├── Redis :6379
└── EC2 :8080
        │
        ▼
http://44.216.160.90:8080
```

### The key commands to remember

```bash
aws configure
aws sts get-caller-identity
```

```bash
ssh -i fedoraos.pem ubuntu@EC2_IP
```

```bash
sudo systemctl enable --now jenkins
```

```bash
sudo systemctl enable --now docker
```

```bash
sudo usermod -aG docker jenkins
```

```bash
ansible app_servers -m ping
```

```bash
docker build -t IMAGE .
```

```bash
docker push IMAGE
```

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg \
ansible-playbook \
-i ansible/inventory.ini \
ansible/deploy.yml \
--extra-vars "docker_image=IMAGE"
```

```bash
sudo docker compose pull
sudo docker compose up -d
sudo docker compose ps
```

```bash
curl http://localhost:8080
```

And finally:

```text
Git push
   ↓
Jenkins
   ↓
Docker build
   ↓
Docker test
   ↓
Docker Hub
   ↓
Ansible
   ↓
EC2 #2
   ↓
Docker Compose
   ↓
Flask + Redis
```

This is the command-level version of the entire AWS/CI/CD setup we worked through.

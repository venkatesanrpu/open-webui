# Bare Ubuntu Server Setup & Docker Installation Guide

Since you are starting with a freshly installed bare Ubuntu system, follow this step-by-step workflow to securely install Docker and prepare your environment for the Open WebUI production deployment.

## Step 1: Update the System Packages
First, connect to your server via SSH. Update the package index and upgrade all existing packages to their latest versions to ensure security and compatibility.

```bash
sudo apt update
sudo apt upgrade -y
```

## Step 2: Install Required Prerequisites
Install packages that allow `apt` to use packages over HTTPS.

```bash
sudo apt install apt-transport-https ca-certificates curl software-properties-common -y
```

## Step 3: Add Docker's Official GPG Key
This ensures that the software you download is authentic.

```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
```

## Step 4: Add the Docker Repository
Add the stable Docker repository to your APT sources.

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

## Step 5: Install Docker Engine and Docker Compose
Update the package index again with the new repository, and install the Docker components.

```bash
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y
```

> [!TIP]
> **Verify the Installation:**
> Run `sudo docker --version` and `sudo docker compose version` to ensure both commands output a version number successfully.

## Step 6: Post-Installation (Run Docker without Sudo)
By default, running Docker commands requires `sudo`. To run them as your regular user, add your user to the `docker` group.

```bash
sudo usermod -aG docker ${USER}
```

> [!IMPORTANT]
> You must **log out and log back in** (or reconnect via SSH) for this group change to take effect. Alternatively, you can run `su - ${USER}`.

> Starting and Enabling Docker
```bash
sudo systemctl start docker
sudo systemctl enable docker
```

> Check Status of the docker
```bash
sudo systemctl status docker
```

> Verify socket exits
```bash
ls -l /var/run/docker.sock
```

## Step 7: Create the Production Directory Structure
Once Docker is ready, create the folders that will house your `compose.yaml` and your persistent data (like the syllabus and database).

```bash
mkdir -p ~/open-webui-production/data/syllabus
mkdir -p ~/open-webui-production/data/db
cd ~/open-webui-production
```

## Step 8: Custom Docker Configuration
```bash
sudo docker compose up -d --build
```

> When you edit python codes in production you dont need to build it again you just need to restart the docker compose `sudo docker compose down` then `sudo docker compose up -d`

> However, if you edit the Frontend (SyllabusExplorer.svelte) or change the Dockerfile version to 0.9.6, you must run the big command again:
```bash
sudo docker compose up -d --build
```

## Next Steps
You will transfer the custom `compose.yaml` and extension files (which we are generating in the workspace) to the `~/open-webui-production` directory on your server. Once transferred, you will simply run `docker compose up -d` to launch the entire platform.

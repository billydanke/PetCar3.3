# PetCar3.3 Raspberry Pi General Installation Guide

## 1. Update Packages
After a fresh installation of Raspberry Pi OS Lite (Trixie-based at the time of writing), you'll want to run the following to ensure everything is up to date before starting:
```sh
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

## 2. Verify/Install Prerequisites
Some of these are likely already installed and up-to-date, but just in case, run the following command:
```sh
sudo apt install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  python3-rpi.gpio \
  i2c-tools \
  python3-smbus \
  libffi-dev \
  libssl-dev
```
This will ensure Git, Python, Python GPIO, and I2C tools are properly installed before we continue. If you'd like, you can check the versions of Python and Git using the following commands:
```sh
python --version
git --version
```

## 2. Create the App Directory
Many of the PetCar3.3 sofrware components, such as the control server and the git repo itself, will exist within an application directory. To make that directory (and set folder ownership to user), run the following commands:
```sh
sudo mkdir -p /opt/petcar33/{app,venv}
sudo chown -R $USER:$USER /opt/petcar33
```
Setting ownership to the user will let you easily run ``git pull`` and make alterations without needing to use sudo.

To check that the folder structure is set up right, use the following command:
```sh
ls /opt/petcar33
```
where you should see ``app/`` and ``venv/`` listed

## 3. Clone the Repository into the App Directory
Once the application folder is made, clone the repo into it:
```sh
git clone https://github.com/billydanke/PetCar3.3.git /opt/petcar33/app
```
Then, you can verify the structure:
```sh
cd /opt/petcar33/app
git status
ls -la
```

## 4. Create the Python Virtual Environment
As of writing, Debian now requires python packages installed via pip to be done so inside of a virtual environment. Because RPi.GPIO was installed via apt, the easiest way to use it inside of the virtual environment is by creating the ``venv`` with access to system site packages. To create the environment, run the following:
```sh
python -m venv --system-site-packages /opt/petcar33/venv
```
and then activate it:
```sh
source /opt/petcar33/venv/bin/activate
```

Inside the virtual environment, upgrade pip and its setup tools:
```sh
pip install --upgrade pip setuptools wheel
```

## 5. Install the Necessary Python Packages
While still inside the virtual environment, run the following to install the necessary python packages for the control server:
```sh
pip install "websockets>=16"
pip install adafruit-circuitpython-servokit
```
Once installed, you can test to make sure things are working:
```sh
python -c "from websockets.asyncio.server import ServerConnection, serve; print('websockets OK')"
python -c "from adafruit_servokit import ServoKit; print('ServoKit OK')"
python -c "import RPi.GPIO as GPIO; print('RPi.GPIO OK')"
```

## 6. Test the Control Server Manually
While still inside the virtual environment, you can test run the control server:
```sh
python "/opt/petcar33/app/Control Server/control_server.py"
```
If everything works, use ``Ctrl+C`` to exit the server and type ``deactivate`` to exit the virtual environment shell.

## 7. Start Control Server at Boot
To start the control server at system boot, we'll be using a systemd service. To do so, run the following to create the service:
```sh
sudo nano /etc/systemd/system/petcar33-control.service
```
and add the following content (be sure to replace the <>'s with your username):
```sh
[Unit]
Description=PetCar3.3 Control Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<Your Username>
Group=<Your Username>
WorkingDirectory=/opt/petcar33/app
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/petcar33/venv/bin/python /opt/petcar33/app/Control\ Server/control_server.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
```

Save and close the file. Next, reload systemd and enable the service:
```sh
sudo systemctl daemon-reload
sudo systemctl enable --now petcar33-control.service
```

If you ever want to check the service status, start, restart, stop, or disable loading the service at boot, the following commands will let you do so:
```sh
sudo systemctl start petcar33-control
systemctl status petcar33-control
sudo systemctl restart petcar33-control
sudo systemctl stop petcar33-control
sudo systemctl disable petcar33-control
```
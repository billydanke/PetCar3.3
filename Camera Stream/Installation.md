# Installation Guide for PetCar3.3 Camera Streaming

## 1. Update Packages
After a fresh installation of Raspberry Pi OS Lite (Trixie-based at the time of writing), you'll want to run the following to ensure everything is up to date before starting:

```sh
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

## 2. Install/Verify RpiCam
You can give it a shot to see if rpicam is already installed, if so you should be able to get the list of connected cameras (make sure you connect the camera beforehand):

```sh
rpicam-hello --list-cameras
```
where you should see a return something like this:
```sh
Available cameras
-----------------
0 : ov5647 [2592x1944 10-bit GBRG] (/base/soc/i2c0mux/i2c@1/ov5647@36)
    Modes: 'SGBRG10_CSI2P' : 640x480 [58.92 fps - (16, 0)/2560x1920 crop]
                             1296x972 [46.34 fps - (0, 0)/2592x1944 crop]
                             1920x1080 [32.81 fps - (348, 434)/1928x1080 crop]
                             2592x1944 [15.63 fps - (0, 0)/2592x1944 crop]
```

If you don't, that's okay. Continue on.

Next, you'll want to run the following to install rpicam and rpicam-hello:
```sh
sudo apt install -y rpicam-apps
```
To verify that it's now installed correctly, you can try both of the following to ensure the camera is detected and that you are recieving data:
```sh
rpicam-hello --list-cameras
rpicam-hello -t 5000
```
If all is well, then this step is complete.

## 3. Install MediaMTX
First, run the following to install the prerequisites:
```sh
sudo apt install -y curl tar jq
```

The latest MediaMTX release can be obtained using the following (This uses GitHub's 'latest release' to keep from hardcoding versions):
```sh
set -e
TAG="$(curl -s https://api.github.com/repos/bluenviron/mediamtx/releases/latest | jq -r .tag_name)"
echo "Latest MediaMTX Version: $TAG"
curl -L -o /tmp/mediamtx.tar.gz "https://github.com/bluenviron/mediamtx/releases/download/${TAG}/mediamtx_${TAG}_linux_arm64.tar.gz"
mkdir -p /tmp/mediamtx_unpack
tar -xzf /tmp/mediamtx.tar.gz -C /tmp/mediamtx_unpack
sudo mv /tmp/mediamtx_unpack/mediamtx /usr/local/bin/
sudo chmod +x /usr/local/bin/mediamtx
```

## 4. Create MediaMTX Configuration
Next, you'll want to create the MediaMTX configuration for the Pi camera and WebRTC. Start by getting the Pi's local IP address. If you don't already know it, you can print it out with the following:
```sh
PI_IP="$(hostname -I | awk '{print $1}')"
echo "PI_IP=$PI_IP"
```

Next, create a .yml configuration file in /usr/local/etc/mediamtx.yml:
```sh
sudo nano /usr/local/etc/mediamtx.yml
```
and insert the following:
```yml
# WebRTC HTTP listener default is :8889
webrtc: yes
webrtcAddress: :8889
webrtcAdditionalHosts: [<Insert your Pi's local IP here>]

# Turn off protocols we don't need right now
rtsp: no
rtmp: no
hls: no
srt: no

paths:
  cam:
    source: rpiCamera
    # Camera tuning settings, you can change this to your desired quality.
    # If you see slowdown or CPU throttling, try lowering the quality down until it streams nicely.
    rpiCameraWidth: 1280
    rpiCameraHeight: 720
    rpiCameraFPS: 15
    rpiCameraCodec: hardwareH264
    rpiCameraBitrate: 1500000
    rpiCameraHardwareH264Profile: baseline
    rpiCameraIDRPeriod: 30
```
Save and close the file, and then you'll probably want to increase the UDP receive buffer size, which can help reduce some streaming freezes. To do so, nano into /etc/sysctl.d/99-network-tuning.conf:
```sh
sudo nano /etc/sysctl.d/99-network-tuning.conf
```
and insert the following two lines:
```
net.core.rmem_default=1000000
net.core.rmem_max=1000000
```
Then run the following to enable it:
```sh
sudo sysctl -p /etc/sysctl.d/99-network-tuning.conf
```

Once that is done, test the MediaMTX WebRTC stream by first starting the server:
```sh
/usr/local/bin/mediamtx /usr/local/etc/mediamtx.yml
```
and then connect to the stream by going to <b>"http://<Your Pi's IP>:8889/cam"</b>.
If you see the video stream, all is well. If you notice that things are a little bit choppy or too low quality for your liking, feel free to play around with the configuration until it's all behaving nicely.

When you're ready, close the MediaMTX server with <b>Ctrl+C</b>.

## 5. Run MediaMTX Server on Boot
You'll likely want the camera streaming to become available as soon as the Pi has finished booting. To do this, create a service using the following:
```sh
sudo nano /etc/systemd/system/mediamtx.service
```
and enter the following:
```sh
[Unit]
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/mediamtx /usr/local/etc/mediamtx.yml
Restart=on-failure
RestartSec=1

[Install]
WantedBy=multi-user.target
```
Then, run the following to enable the service:
```sh
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx
```

Lastly, if you ever want to take a look at what the server is doing, you can do so using this command:
```sh
journalctl -u mediamtx -f
```
which will give you realtime logs for the service.

## 6. Final Notes
That is all you need for the WebRTC camera streaming setup. After the Raspberry Pi has completed booting and connecting to the network, you should always be able to access the camera stream in your browser. If you'd like to implement your own control page, you can easily embed the camera stream into your page using an iframe element.

Thanks and have fun :)
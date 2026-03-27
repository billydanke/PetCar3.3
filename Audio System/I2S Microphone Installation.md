# Installation Guide for PetCar3.3 I2S Microphone

This guide assumes that the initial Camera Streaming installation and initial I2S speaker installation has already been performed. If not, it is recommended that you do so before continuing this guide.

## 1. Update Packages
After a fresh installation of Raspberry Pi OS Lite (Trixie-based at the time of writing), you'll want to run the following to ensure everything is up to date before starting:

```sh
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

## 2. Install GStreamer
GStreamer will allow the camera and audio to be linked together before being streamed over WebRTC to be viewed. To install it, use the following command:

```sh
sudo apt install -y \
  gstreamer1.0-tools \
  gstreamer1.0-alsa \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-libcamera \
  gstreamer1.0-rtsp
```

## 3. Enable the INMP441 I2S Microphone Overlay
To use the I2S microphone(s), you'll need to enable them in the boot configuration. To do so, edit `/boot/firmware/config.txt` file using the following command:
```sh
sudo nano /boot/firmware/config.txt
```
where you'll want to add the following below the previously added `max98357a,no-sdmode=1` line:
```sh
# Enables the I2S microphone(s)
dtoverlay=googlevoicehat-soundcard
```

Google Voice Hat is the recommended overlay to allow for both input and output of audio over I2S. This way, you can take in microphone data and send out data to the previously set up speaker amplifier at the same time.

Once you have made the necessary configuration changes, save and close the file and disconnect power before continuing to the next step.

## 4. Physically Connect the INMP441 I2S Microphone(s)
First, ensure that you have powered down the Raspberry Pi and/or disconnected power from the PetCar3.3 mainboard. Once you have done so, make the following physical wiring connections between the INMP441 microphone (shown on left) and the Raspberry Pi (shown on right):

```
WS          <-->    GPIO19 (pin 35, also labelled PCM_FS)
SCK         <-->    GPIO18 (pin 12, also labelled PCM_CLK)
SD (data)   <-->    GPIO21 (pin 40, also labelled PCM_DOUT)
GND         <-->    GND (ideally use the mainboard's GND rail)
VDD         <-->    3.3V (ideally use the mainboard's 3.3V rail)
```
INMP441 microhpones support a Left/Right channel, meaning that you can connect two microphones to act as one stereo audio input. If you are using two microphones, make the following connections:

```
Left Microphone:
  L/R Pin   <-->    GND (ideally use the mainboard's GND rail)

Right Microphone:
  L/R Pin   <-->    3.3V (ideally use the mainboard's 3.3V rail)
```
Otherwise, if you are using a single microphone to use as a mono audio input, you can simply `Connect the L/R Pin to GND`.

As mentioned above, for 3.3V, GND, and L/R, it's best to use the PetCar3.3 mainboard's power rails, as it will allow you to power more peripherals down the line.

Once the microhone connections are made, you can now reconnect power to the PetCar3.3 mainboard and/or the Raspberry Pi.

## 5. Modify the MediaMTX Configuration
In order to stream both video and audio, a separate stream will be made to combine the two sources together. To start, open the configuration file with the following command:
```sh
sudo nano /usr/local/etc/mediamtx.yml
```
and make the following modifications:
```yml
# Change this from no to yes.
rtsp: yes

# Add the following:
cam_audio:
    runOnInit: >
      gst-launch-1.0
      rtspclientsink name=s location=rtsp://127.0.0.1:8554/cam_audio protocols=tcp
      rtspsrc location=rtsp://127.0.0.1:8554/cam latency=0 !
      rtph264depay ! h264parse ! queue ! s.
      alsasrc device=hw:0 !
      audioconvert ! audioresample !
      volume volume=5 !
      opusenc bitrate=48000 !
      queue ! s.
    runOnInitRestart: yes
```

This launches a new path, combining the video and audio together using GStreamer. Ensure your hardware device is correct by changing the number in `hw:0` to match the hardware device returned by running `arecord -l` (however, since this is likely the only microphone attached, it will likely be device 0). You can also modify the volume control in `volume volume=5` until the audio is being picked up at a nice volume without too much background static.

Once the changes have been made, restart the service with the following command:
```sh
sudo systemctl restart mediamtx
```

At this point, you should now be able to reach the audio/video stream by changing the previously used path `/cam` with `/cam_audio` in the client control page. Note that the video element will likely start muted due to typical web browser regulations. Unmute the video, and check to see if audio is coming through properly.

## 6. Final Notes
That should be everything you need to get the microphones communicating with the Raspberry Pi. As mentioned earlier, if the volume is too quiet or too loud, you can adjust the volume to reach the desired level.

Hopefully this all worked for you. From here, PetCar3.3 will now be able to stream the voices of those around it. Thanks and have fun :)
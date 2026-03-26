wire the mic(s).

install all the gstreamer things:

sudo apt update
sudo apt install -y \
  gstreamer1.0-tools \
  gstreamer1.0-alsa \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-libcamera \
  gstreamer1.0-rtsp


add the overlay in boot config for the mics:

in /boot/firmware/config.txt:
dtoverlay=googlevoicehat-soundcard

update the mediamtx config yml file, and restart the service (/usr/local/etc/mediamtx.yml):

rtsp: yes

cam_audio:
    runOnInit: >
      gst-launch-1.0
      rtspclientsink name=s location=rtsp://127.0.0.1:8554/cam_audio protocols=tcp
      rtspsrc location=rtsp://127.0.0.1:8554/cam latency=0 !
      rtph264depay ! h264parse ! queue ! s.
      alsasrc device=hw:0 !
      audioconvert ! audioresample !
      volume volume=5 !
      opusenc bitrate=64000 !
      queue ! s.
    runOnInitRestart: yes
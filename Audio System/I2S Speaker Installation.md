# Installation Guide for PetCar3.3 I2S Speaker

## 1. Update Packages
After a fresh installation of Raspberry Pi OS Lite (Trixie-based at the time of writing), you'll want to run the following to ensure everything is up to date before starting:

```sh
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

## 2. Install/Verify Alsa-Utils
You may already have alsa-utils installed, if so you can continue to the next step. To check if you have it installed, or to otherwise install it, run the following command:
```sh
sudo apt install -y alsa-utils
```

## 3. Enable the MAX98357A I2S Amp
To use the I2S amp, you'll need to enable it in the boot configuration. To do so, edit the <b>/boot/firmware/config.txt</b> file using the following command:
```sh
sudo nano /boot/firmware/config.txt
```
where you'll want to make the following changes to the file. First, check to make sure <b>dtparam=audio=off</b>. If it's currently on, you can disable it, since we'll be bypassing this with I2S. Next, make the following changes at or near the end of the file:
```sh
# Enables the I2S audio amp
dtparam=i2s=on
dtoverlay=max98357a,no-sdmode=1
```
<b>A quick note on the 'no-sdmode=1':</b> The SD pin on the amplifier is an enable pin. This guide assumes you want the amplifier enabled at all times, so it intentionally ignores the SD pin and assumes that you've tied the physical amp SD pin to a 3.3V line. If you want a software-controlled amp-enable, you can instead use 'sdmode-pin=13', where 13 is an example pin. If you leave it blank, aka 'sdmode-pin', it will default to GPIO4 (which is likely already being used depending on your setup, so make sure you set it to a currently-unused pin).

Once you have made the necessary configuration changes, save and close the file and disconnect power before continuing to the next step.

## 4. Physically Connect the MAX98357A I2S Amp
First, ensure that you've powered down the Raspberry Pi and/or disconnected power from the PetCar3.3 mainboard. Once you have done so, make the following physical wiring connections between the MAX98357A amplifier (left) and the Raspberry Pi (right):

```
LRC         <-->    GPIO19 (pin 35, also labelled PCM_FS)
BCLK        <-->    GPIO18 (pin 12, also labelled PCM_CLK)
DIN (data)  <-->    GPIO21 (pin 40, also labelled PCM_DOUT)
GAIN        (leave disconnected for default gain)
SD          <-->    3.3V (ideally use the mainboard's 3.3V rail)
GND         <-->    GND (ideally use the mainboard's GND rail)
Vin         <-->    5V (ideally use the mainboard's 5V rail)
```

As mentioned above, for SD, GND, and Vin, it's best to use the PetCar3.3 mainboard's power rails, as it will allow you to power more peripherals down the line (plus, these rails were added specifically for things like this). Notice also that Vin is set to 5V. This is because the 5V line comes directly from the main voltage step-down converter, and is capable of drawing significantly more current compared to the 3.3V line, which piggybacks off of the Raspberry Pi's internal 3.3V regulator (maximum current is ~300mA).

Once the amp connections are made, connect the speaker wires into the matching positive/negative screw terminals on the other end of the amp, and you're good to go hardware-wise. You can now reconnect power to the PetCar3.3 mainboard and/or the Raspberry Pi.

## 5. Configuring Sound Settings
Once the board is powered back on, run the following command and ensure you see the MAX98357A listed in the device list:
```sh
aplay -l
```

You should see something like this:
```sh
**** List of PLAYBACK Hardware Devices ****
card 0: MAX98357A [MAX98357A], device 0: bcm2835-i2s-HiFi HiFi-0 [bcm2835-i2s-HiFi HiFi-0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 1: vc4hdmi [vc4-hdmi], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
```
Notice that in this example, two cards exist. This is okay, but take note of which card number and device number the MAX98357A is set to. In the case of the example, both the card and device number is 0.

If your card/device numbers are something other than 0, run the following command to create a config file to alter the default audio output (you can ignore this otherwise):
```sh
sudo nano /etc/asound.conf
```
and input the following:
```sh
defaults.pcm.card <your card number>
defaults.ctl.card <your card number>
```

Next, run an audio test to check if everything is working properly so far (be aware that this will play at full volume, but isn't deafeningly loud):
```sh
aplay /usr/share/sounds/alsa/Front_Center.wav
```

Next, check to see if hardware volume control exists. In many cases it won't. That's okay, as we will go over how to set up a software volume setting next. To check, run the following command:
```sh
amixer scontrols
```
If <b>'Master', 'PCM', 'Digital'</b> or anything else comes up in the list, your board supports hardware volume, and you can skip forward past software volume control. If nothing comes up, then you'll need to implement volume through software.

To do this, we'll start by editing asound.conf:
```sh
sudo nano /etc/asound.conf
```
and inserting the following (make sure to replace the relevant <>'s with your card/device numbers):
```sh
pcm.softvol {
  type softvol
  slave.pcm "plughw:<card number>,<device number>"
  control {
    name "SoftMaster"
    card <card number>
  }
  min_dB -50.0
  max_dB 0.0
}

pcm.!default {
  type plug
  slave.pcm "softvol"
}

ctl.!default {
  type hw
  card <card number>
}
```
Save and close the file. Software volume should now work, but you may need to re-run the audio sample to initialize it:
```sh
aplay /usr/share/sounds/alsa/Front_Center.wav
```
Then, you can rerun <b>'amixer scontrols'</b>, where it should appear as 'SoftMaster'. To view and control the volume in a nicer way, you can use the following command to open alsamixer, which uses up and down arrow keys to raise and lower the volume:
```sh
alsamixer
```
You can also directly control the volume level using the following command:
```sh
amixer sset 'SoftMaster' 60%
```
where the percentage is between 0-100.

## 6. Final Notes
That should be everything you need to get the Raspberry Pi's audio to output via I2S to a speaker. As mentioned earlier, if the SoftMaster volume control doesn't appear immediately, you may need to re-run the audio sample for it to recognize the new control (at least I did in the creation of this guide).

Also, if you decided to use an enable GPIO pin for the amp's SD connection, make sure to raise your selected pin to 3.3V when you want to output audio, as otherwise the amp will be disabled.

Hopefully this all worked for you. From here, the PetCar3.3 Python control script will now be able to output audio to those around it. Thanks and have fun :)
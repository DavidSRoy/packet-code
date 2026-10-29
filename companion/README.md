# CV companion (Raspberry Pi Zero 2 WH)

The Pi reads the box-lid tags with the USB camera and talks MAVLink to the
Pixhawk 6X. The Pixhawk drives the gripper servo. The Pi asks for servo moves
over MAVLink, so the servo stays under the FC failsafes and is in the logs.

## SD card

- Raspberry Pi OS Lite 64-bit (Trixie, 2026-10-06), set up by cloud-init.
- Hostname `packet-cv` (`ssh packet@packet-cv.local`). SSH key login only. No password.
- `config.txt`: `enable_uart=1`, `dtoverlay=disable-bt`. The full UART is on
  GPIO14/15 as `/dev/serial0`. Bluetooth is off.
- `cmdline.txt`: no serial console, so the UART is free for MAVLink.
- First boot installs OpenCV, pymavlink and v4l-utils. It copies this folder to
  `/home/packet/companion`. The log is `/var/log/packet-setup.log`.

## Wiring

| From | To | Note |
|---|---|---|
| 6X TELEM3 pin 2 (TX) | Pi GPIO15 RXD (pin 10) | 3.3 V logic on both sides. Cross TX and RX |
| 6X TELEM3 pin 3 (RX) | Pi GPIO14 TXD (pin 8) | |
| 6X TELEM3 pin 6 (GND) | Pi GND (pin 6 or 14) | Do not connect TELEM3 pin 1 (5 V) |
| 5 V BEC, 2.5 A or more | Pi 5V (pin 2) + GND (pin 14) | Do not use the TELEM 5 V pin |
| Arducam OV9281 USB (B096M5DKY6) | Pi micro-USB data port (the inner one, "USB") | Needs a micro-USB OTG adapter. 1280x800, 70 deg HFOV |
| 6X AUX5 signal (SERVO13) | Servo signal | |
| 7.4 V BEC, 5 A or more | Servo + and - | The 6X servo rail has no power. Servo range is 4.8-8.4 V |

## FC parameters

Applied on 2026-10-24 (link tested: heartbeat and about 100 msg/s on the Pi):

| Param | Value | Why |
|---|---|---|
| `SERIAL5_PROTOCOL` | 2 | MAVLink2 on TELEM3 |
| `SERIAL5_BAUD` | 921 | 921600 baud |
| `BRD_SER5_RTSCTS` | 0 | 3-wire link, no flow control |

NOT applied (need Jason's OK):

| Param | Value | Why |
|---|---|---|
| `SERVO13_FUNCTION` | 28 | Gripper |
| `GRIP_ENABLE` | 1 | then set `GRIP_GRAB` / `GRIP_RELEASE` PWM on the bench |

SERVO13-14 are their own timer group on the 6X, so 50 Hz servo PWM does not
change the DShot motor outputs on SERVO9-12.

## Tests

```bash
cd ~/companion
v4l2-ctl --list-formats-ext          # check the camera
.venv/bin/python cam_tags.py --frames 50 --save /tmp/tags.jpg
.venv/bin/python fc_link.py          # listen only
.venv/bin/python fc_link.py --servo 13 --pwm 1500   # props off
```

Option: the Pi can make servo PWM itself on GPIO18 (pin 12). Uncomment
`dtoverlay=pwm,pin=18,func=2` in `config.txt`. The FC path is preferred.

## Box-lid stickers

`python3 lid_stickers.py --boxes 1-12 --out stickers` makes one 300 x 200 mm
SVG per box, `stickers/lid_stickers.pdf` (one page per box, 1:1 scale) and
`stickers/lid_layout.json` (tag corner positions for the pose).

| Tag | Family | Size | ID | Use |
|---|---|---|---|---|
| Centre | ArUco 4x4_50 | 168 mm (28 mm cells) | box number (0-49) | box ID from far away |
| 4 corners | AprilTag 36h11 | 40 mm (5 mm cells) | 4n .. 4n+3 (TL, TR, BR, BL) | final position and yaw |

`lid_tags.py` finds every box in view and gives its ID and pose. It puts all
visible tags of one box into one solvePnP.

Simulated results with the earlier OV2311 camera (B0322, 1600x1200, 75 deg).
The OV9281 has about 12 % fewer pixels per degree, so the ID range is about
12 % shorter. Blur, noise, MJPEG, no motion blur, no glare:

| Camera height | Result |
|---|---|
| 4-10 m | ID found. Position error 0.6 % (4 m) to 6 % (10 m) of range |
| 6 m, two boxes | Both IDs found |
| 0.18-1.3 m | Pose error under 1 cm |
| Below about 0.16 m | No full tag in view: the landing-gear funnel does the rest |

Printing:
- Print at 100 % scale (no "fit to page"). Check the 50 mm bar and the 168 mm big-tag edge.
- Use matte white vinyl. Gloss gives glare and the tags then fail.
- Keep the white margins clean. Do not put logos or text near the tags.
- Put the sticker on the lid with the "BOX nn" text on the left when you look down at the lid.

## Camera

- Arducam OV9281 mono global shutter, UVC, MJPG 1280x800. The scripts use
  1280x800 and 70 deg HFOV by default.
- Focus: set the M12 lens sharp at about 6 m (or infinity), then lock it with
  glue. With focus at infinity, the blur stays at about 0.27 of a corner-tag
  cell at all distances, also at 0.1 m, because the tags grow at the same rate.
- Live view: `cam_stream.py` (service `packet-cam`) captures raw YUYV
  (C270: 1280x720 at 10 fps). Detection uses the Y plane on the full frame
  at about 5 Hz (one pass for both tag types, OpenCV 4.12; 7 threshold windows 3-63 px for the landing light and all heights). The video is hardware H.264 at `/h264`; the
  ground-control page decodes it with WebCodecs. There is no JPEG step.
- The earlier OV2311 (B0322) gave only empty UVC headers and no image (USB link
  good, sensor gave no frames). It went back as defective.
- The SD card has `dtoverlay=dwc2,dr_mode=host` in `config.txt` from the
  OV2311 tests. It is not proven necessary.

## Wi-Fi and status screen

cloud-init applies `network-config` on the first boot only. To add or change
a network later, edit `packet/wifi.txt` on the SD card (on a Mac):

```
# SSID|PASSWORD|PRIORITY   (higher priority is tried first)
UW MPSK|<device passphrase>|20
```

At every boot, `wifi_join.sh` adds these networks to NetworkManager (with the
fixed MAC that UW MPSK needs) and connects.

### Drone hotspot (video to the laptop without a shared network)

An `AP` line makes the Pi its own Wi-Fi network (2.4 GHz WPA2, Pi at
`10.42.0.1`, DHCP for the laptop):

```
# AP|SSID|PASSWORD|PRIORITY   (password: 8 or more characters)
AP|PacketDrone|<password>|0
```

- The hotspot is always "in range". With priority 0 it starts only when no
  listed network is in range at boot; with the highest priority it always starts.
- Its DHCP gives no gateway and no DNS (`/etc/NetworkManager/dnsmasq-shared.d/packet-ap.conf`),
  so the laptop keeps its internet on iPhone USB or Ethernet.
- The Pi sends `10.42.0.1` over the radio (PIIP), so the ground-control page
  finds the video by itself.
- Needs `dnsmasq-base` (`setup.sh` installs it; on a Pi set up before 2026-10-29:
  `sudo apt-get install dnsmasq-base`).

On the Mac:

```bash
tools/drone_wifi.sh join PacketDrone <password>   # joins, checks http://10.42.0.1:8080
tools/drone_wifi.sh check
tools/drone_wifi.sh leave PacketDrone             # back to the usual Wi-Fi
```

Test: `bash companion/test/wifi_join_test.sh` (fake nmcli, 9 checks). `setup.sh` runs again at each boot
until it finishes. (The HDMI `status_screen.sh` was removed on 2026-10-25: it ran
`cloud-init status`, `nmcli` and a DNS lookup every 5 s, about 1 CPU core, and
the drone has no screen.)
Never commit `wifi.txt`; `.gitignore` blocks it.

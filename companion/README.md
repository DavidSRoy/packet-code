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

X1C box (BX-005 v12, inside 218 mm; lid BX-006 v7, 225.6 x 206.4 mm lid top):
`stickers_218x200/` is the 218 x 200 mm set. Centre ArUco 108 mm (18 mm cells),
four 30 mm AprilTag corners (3.75 mm cells) and ten more 30 mm AprilTags
(IDs 200 + 10n .. 200 + 10n + 9): three more along each long edge (a row of five
with the corners) and two on each short edge. Boxes 0-38 only (36h11 stops at
ID 586). When these stickers go on, run
`cam_stream.py --layout stickers_218x200/lid_layout.json` (or copy that file to
`lid_layout.json`). Remake:

```bash
python3 lid_stickers.py --boxes 1-12 --out stickers_218x200 --size 218x200 \
  --big-cell 18 --small-cell 3.75 --inset 5 \
  --extra "-44.5,80;0,80;44.5,80;-44.5,-80;0,-80;44.5,-80;-89,36;-89,-36;89,36;89,-36"
```

Camera mount for this set (Master v60, `tools/sim/`): C920 on the left side of
the body (mount K), lens 40 mm ahead of and 120 mm left of the frame centre
(between the two left arms, 45 mm out from the landing leg), 40 mm below the
frame origin, pointing straight down, image top toward the nose. The right side
at (-40, -120) is the same spot turned 180 deg. Spots under a propeller disc
(15 in props + 20 mm) are left out for the downwash. Simulated, 40 misaligned
descents per height: 39-40/40 from 3 m to 0.32 m, 36/40 at 0.27 m, 28/40 at
0.20 m, 20/40 at 0.17 m (side mount D at 70, 95, -100: 24/40 at 0.20 m, 6/40 at
0.17 m; old mount at 134, 0, -112 under the GPS mast, right above gripper jaw 2:
26/40 at 3 m, 16/40 at 0.45 m, 0/40 at 0.17 m). Under the rear-left arm tilted
25 deg in (mount J) is a little better at 0.20 m (36/40) but sits under a prop.

Simulator (`tools/sim/`, needs opencv-python >= 4.12, numpy, matplotlib; ffmpeg for video):
- `lid_camera_sim.py --mounts K,D --snap`: scored descents with the real detector.
- `mount_sweep.py --cam C920`: search lens spots and tilts; `sweep_map.py` draws the result.
- `descent_video.py --out descent.mp4`: video of one descent (camera image, rear and top views).
- `lid_camera_viewer.html`: interactive 3D page (open in a browser): move the camera, fly the descent.

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
fixed MAC that UW MPSK needs) and connects. `setup.sh` runs again at each boot
until it finishes. (The HDMI `status_screen.sh` was removed on 2026-10-25: it ran
`cloud-init status`, `nmcli` and a DNS lookup every 5 s, about 1 CPU core, and
the drone has no screen.)
Never commit `wifi.txt`; `.gitignore` blocks it.

### Video in the field: the Mac's Wi-Fi network

With no shared network, the Mac makes one with Internet Sharing (`PacketGround`)
and the Pi joins it. The Mac gets its internet from an iPhone on USB (map tiles,
cloud push, TFR refresh). The Mac is `192.168.2.1`; the Pi gets `192.168.2.x`
and sends it over the radio, so the page finds the video by itself.

One time:

- Mac, System Settings > General > Sharing > Internet Sharing (i), with the
  toggle off: share from **iPhone USB**, to **Wi-Fi** only. Wi-Fi Options: name
  `PacketGround`, channel **1, 6 or 11** (the Pi Zero 2 W has no 5 GHz),
  WPA2/WPA3 Personal (macOS has no WPA2-only choice), password.
- Pi, `wifi.txt`, with a priority above all other lines:
  ```
  PacketGround|<password>|40
  ```

Before each flight:

1. Plug the iPhone and the telemetry radio directly into the Mac, not into a
   shared hub (on 2026-10-29 both dropped off USB together more than once).
   Turn on Personal Hotspot.
2. Mac Wi-Fi: **Auto-Join off** for the usual networks, then Wi-Fi off and on.
   Wi-Fi must show "Not Associated": when the Mac joins a network with internet,
   the iPhone USB link stops, and Internet Sharing has no source.
3. Internet Sharing off, then on. Check (bridge100 at 192.168.2.1, `bootpd`,
   internet on the iPhone):
   ```bash
   ifconfig bridge100 | grep inet; pgrep -l bootpd; route -n get default | grep interface
   ```
4. Power the drone. Start `ground_control/server.py`. The camera panel shows
   `WI-FI · 10 FPS` within about 1 min of the Pi boot.

Known limits (2026-10-29):

- The Wi-Fi driver as loaded at boot does not join this network ("Authentication
  timed out"; macOS offers WPA2/WPA3 and the Pi tries WPA3). After one driver
  reload it joins with WPA2, so `wifi_join.sh` reloads the driver at each boot.
  The cause is not known. A reboot with this in place is not tested yet.
- The Mac network restarted every few minutes in the test (new MAC address each
  time). The Pi retries forever (`autoconnect-retries 0`); in between, the page
  shows the radio snapshots.
- **Switch to the Pi hotspot** (the Pi makes a WPA2-only network, the Mac joins
  it) when this is not reliable enough. That code is the reverted first version
  of [PR #2](https://github.com/sanjanas18/packethw/pull/2) (commit `1081934`
  and the next three).

Without the iPhone (not tested): no map tiles, no cloud push, and TFRs from the
cache only.

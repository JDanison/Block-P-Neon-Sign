#!/bin/sh
# Block P touch screen: the sign app fullscreen in Chromium. The kiosk session's autostart runs this
# under lwrespawn, so it relaunches within a second if Chromium ever exits.

# Wait for the sign server (it starts at boot as blockp.service)
until curl -s -o /dev/null http://127.0.0.1/api/state; do sleep 1; done

# Profile lives in RAM: nothing is written to the SD card, and it starts fresh every boot
P="/run/user/$(id -u)/blockp-chromium"

exec chromium --ozone-platform=wayland --kiosk --noerrdialogs --disable-infobars --no-first-run \
  --autoplay-policy=no-user-gesture-required --user-data-dir="$P" --disk-cache-dir="$P/cache" \
  --password-store=basic --disable-pinch --overscroll-history-navigation=0 \
  --disable-features=Translate,TranslateUI,OverscrollHistoryNavigation --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 --remote-debugging-port=9222 \
  "http://127.0.0.1/?screen=1"

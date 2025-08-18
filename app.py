# app.py

import sys
import threading
from datetime import datetime, timezone, timedelta

from PyQt5.QtCore import QTimer, QObject, pyqtSignal, QThread, pyqtSlot, Qt
from PyQt5.QtWidgets import QApplication, QMessageBox
from functools import partial

from interface import AddressForm
from googleAPI import addressToCoordinates, getStreetView
from TEJapanAPI import find_and_download_flood_data
from preprocessNCFile import (
    openClosestFile,
    getNearestValueByCoordinates,
    buildDepthPatch,
)
from constants import TEJapanFileType, WebDirectory
from zoneinfo import ZoneInfo

from pythonToJS import start_node, sendToNode, wait_health, _wait_and_send
from imageUtility import save_images
from sse_masks import start_mask_watcher, on_mask_ready


from utility import _get_raw_info,_split_prompts, _ensure_aware, _fmt_dt, _is_no_pano_error,dateConverter,_human_hours
# --------------------------- global state ---------------------------

ACTIVE_UUIDS = set()
JST = ZoneInfo("Asia/Tokyo")
UTC = timezone.utc


BASE_URL = f"http://{WebDirectory.HOST.value}:{WebDirectory.PORT.value}"
API_URL  = BASE_URL + WebDirectory.CAMERA_METADATA_ROUTE.value


class UiBus(QObject):
    ai_ready   = pyqtSignal(bytes)   # bytes for the right panel
    tiles_ready = pyqtSignal()
    progress   = pyqtSignal(str)     # log text lines



class FormWorker(QObject):
    progress = pyqtSignal(str)
    tiles = pyqtSignal(list, list)  # images, metas
    depth = pyqtSignal(float, object, object, str, tuple)  # value, dt_fetched, depth_time, resolution, (coords, lat, lng, size)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, data):
        super().__init__()
        self.data = data

    @pyqtSlot()
    def run(self):
        try:
            # 1) Build the address and geocode
            address = " ".join([self.data["prefecture"], self.data["city"], self.data["town"], self.data["address2"]])
            coords = addressToCoordinates(address)

            # 2) Time conversion
            target_dt_utc, target_dt_jst = dateConverter(self.data)

            # 3) Fetch Street-View (exit early if none found)
            try:
                tiles, metas = getStreetView(
                    coords,
                    target_date=self.data["date"],
                    mode=self.data["mode"],
                    tolerance_m=15,
                    width=640,
                    height=640,
                )
            except Exception as e:
                if _is_no_pano_error(e):
                    self.error.emit("__NO_PANO__")
                    return
                self.error.emit(str(e))
                return

            saved = save_images(tiles)
            for meta, s in zip(metas, saved):
                meta["type"] = "camera"
                meta["uuid"] = s["uuid"]

            self.tiles.emit(tiles, metas)

            # 4) Depth
            if self.data.get("depth_override_enabled"):
                depth_value = float(self.data.get("depth_override_value", 0.0))
                dt_fetched = None
                depth_time = None
                resolution = "override"
            else:
                dt_fetched, resolution = find_and_download_flood_data(target_dt_utc)
                if dt_fetched is None or resolution is None:
                    self.error.emit("__NO_FORECAST__")
                    return


                ds_depth = openClosestFile(TEJapanFileType.DEPTH, target_dt_utc)
                depth_value, depth_time = getNearestValueByCoordinates(ds_depth, coords, target_dt_utc)

            self.depth.emit(
                float(depth_value),
                dt_fetched,
                depth_time,
                resolution,
                (coords, metas[0]["lat"], metas[0]["lng"], metas[0]["size"])
            )

        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

# --------------------------- GUI-thread orchestration ---------------------------

def handle_form(data):
    """
    Turn on waiting animation and start a worker thread.
    Keep a strong reference to the QThread so it isn't destroyed early.
    """
    w.connector.reset(quiet=False)

    thread = QThread()
    thread.setObjectName(f"FormWorker-{len(w._threads)+1}")
    worker = FormWorker(data)
    worker.moveToThread(thread)

    # start work
    thread.started.connect(worker.run)

    # route results back to GUI
    worker.tiles.connect(_on_tiles_from_worker, type=Qt.QueuedConnection)
    worker.depth.connect(_on_depth_from_worker, type=Qt.QueuedConnection)
    worker.error.connect(_on_worker_error, type=Qt.QueuedConnection)

    # cleanup: when finished, quit thread and drop our strong reference
    def _cleanup():
        try:
            thread.quit()
            thread.wait(5000)
        finally:
            try:
                w._threads.remove(thread)
            except ValueError:
                pass
            worker.deleteLater()
            thread.deleteLater()

    worker.finished.connect(_cleanup, type=Qt.QueuedConnection)
    w._threads.append(thread)
    thread.start()

def _on_tiles_from_worker(tiles, metas):
    # Update which UUIDs are "active" for SSE/mask routing
    ACTIVE_UUIDS.clear()
    for m in metas:
        ACTIVE_UUIDS.add(m["uuid"])

    # Show Street-View images and start the map
    w.set_street_images(tiles, metas)
    w.ensure_map_started()

    # Log a concise metadata summary
    w.log.append("\n[Street-View Metadata]")
    def _num(val, places=0):
        try: return f"{float(val):.{places}f}"
        except Exception: return "n/a"
    def _num6(val):
        try: return f"{float(val):.6f}"
        except Exception: return "n/a"
    for m in metas:
        w.log.append(
            f"Camera lat&lng: {_num6(m.get('lat'))}, {_num6(m.get('lng'))}\n"
            f"Heading & Pitch: {_num(m.get('heading'),0)}° / {_num(m.get('pitch'),0)}°\n"
            f"FOV & Size: {_num(m.get('fov'),0)} / {m.get('size')}\n"
            f"Pano date: {m.get('date')}\n"
            f"Address lat&lng: {m.get('location')}\n"
            f"Distance to addr: {_num(m.get('distance_m'),1)} m\n"
        )

    # Send camera metas to the Node viewer (off the GUI thread)
    threading.Thread(target=_wait_and_send, args=(API_URL,bus,metas, "Street-View metadata"), daemon=True).start()

def _on_depth_from_worker(depth_value, dt_fetched, depth_time, resolution, packed):
    coords, lat, lng, size = packed

    # TE-JAPAN log (in JST)
    w.log.append("\n[TE-JAPAN DATA]")
    if resolution:
        w.log.append(f"Resolution: {resolution}")
    if dt_fetched:
        try:
            # Estimate lead time relative to current form selection
            dt_str = f"{w.date_edit.date().toString('yyyy-MM-dd')} {w.time_edit.time().toString('HH:mm')}"
            target_naive = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            target_aware = target_naive.replace(tzinfo=UTC)
            lead_td = _ensure_aware(target_aware, UTC) - _ensure_aware(dt_fetched, UTC)
            w.log.append(f"Lead time: {_human_hours(lead_td)}")
        except Exception:
            pass
        w.log.append(f"Model run: {_fmt_dt(dt_fetched, 'JST')} (JST)")
    if depth_value is not None and depth_time is not None:
        w.log.append(f"Flood depth: {float(depth_value):.2f} m @ {_fmt_dt(depth_time, 'JST')} (JST)\n")

    # Send depth to the browser (off the GUI thread)
    depth_payload = {
        "type": "depth",
        "value": float(depth_value),
        "location": coords,
        "lat": lat,
        "lng": lng,
        "size": size,
    }
    threading.Thread(target=_wait_and_send, args=(API_URL,bus,depth_payload, "flood depth"), daemon=True).start()

def _on_worker_error(msg):
    if msg == "__NO_PANO__":
        w.log.append("⚠ No Street-View panorama found on/before the selected date near this address.")
        QMessageBox.information(w, "No panorama found",
                                "No Street-View panorama was found on/before the selected date near this address.")
    elif msg == "__NO_FORECAST__":
        w.log.append("⚠ No forecast data is available for the selected hour.\n")
        QMessageBox.information(w, "No forecast",
                                "No forecast data is available for the selected hour.\n"
                                "Try a different time (3-hour steps) or wait for a later run.")
    else:
        w.log.append(f"⚠ Error: {msg}")
        QMessageBox.warning(w, "Error", msg)

    w.connector.reset(quiet=True)
    w.submit_btn.setEnabled(True)

# --------------------------- shutdown hygiene ---------------------------

def _graceful_shutdown():
    """
    Ensure all QThreads finish before process exits to avoid:
    'QThread: Destroyed while thread is still running'
    """
    # stop worker QThreads
    for t in list(getattr(w, "_threads", [])):
        try:
            t.requestInterruption()
        except Exception:
            pass
        t.quit()
        t.wait(5000)
        try:
            w._threads.remove(t)
        except ValueError:
            pass

    # stop/join SSE watcher thread if present
    try:
        if "mask_thread" in globals() and mask_thread and mask_thread.is_alive():
            # if start_mask_watcher supports a stop/cancel, call it here.
            # otherwise, just join with a small timeout to avoid zombie threads.
            mask_thread.join(timeout=2.0)
    except Exception:
        pass

# --------------------------- main ---------------------------

if __name__ == "__main__":
    start_node()
    wait_health(BASE_URL + "/health")

    app = QApplication(sys.argv)

    bus = UiBus()  # create after QApp
    w = AddressForm()
    w._threads = []  # strong refs to active QThreads

    bus.ai_ready.connect(w.display_ai_image, type=Qt.QueuedConnection)
    bus.tiles_ready.connect(w.on_tiles_ready, type=Qt.QueuedConnection)
    bus.progress.connect(w.log.append, type=Qt.QueuedConnection)
    w.data_submitted.connect(handle_form, type=Qt.QueuedConnection)

    def _start_sse():
        global mask_thread
        mask_cb = partial(on_mask_ready, ACTIVE_UUIDS=ACTIVE_UUIDS, bus=bus)
        mask_thread = start_mask_watcher(BASE_URL, mask_cb)

    QTimer.singleShot(0, _start_sse)   # schedule once UI is up
    app.aboutToQuit.connect(_graceful_shutdown)

    w.show()
    sys.exit(app.exec_())

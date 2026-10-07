"""
ESP-Linker Web Dashboard
(c) 2025 SK Raihan / SKR Electronics Lab - All Rights Reserved.

Modern, responsive browser-based hardware control and diagnostics dashboard
supporting ESP8266 and ESP32 architectures with real-time telemetry, GPIO matrix,
I2C bus scanner, OTA flasher, and interrupt event monitor.
"""

import json
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

try:
    from flask import Flask, render_template_string, jsonify, request, Response
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

from .device_manager import get_device_manager
from .espboard import ESPBoard
from .utils import discover_devices, format_uptime, format_memory


class Dashboard:
    """Modern web dashboard for ESP-Linker devices"""

    def __init__(self, host: str = 'localhost', port: int = 8080):
        self.host = host
        self.port = port
        self.app = None
        self.manager = get_device_manager()

        if not FLASK_AVAILABLE:
            raise ImportError("Flask is required for the dashboard. Install with: pip install flask")

    def create_app(self):
        """Create Flask application and configure real hardware API routes"""
        self.app = Flask(__name__)

        @self.app.route('/')
        def index():
            return render_template_string(DASHBOARD_HTML)

        @self.app.route('/api/devices')
        def api_devices():
            devices = self.manager.list_devices()
            return jsonify([d.to_dict() for d in devices])

        @self.app.route('/api/devices/discover', methods=['POST'])
        def api_discover():
            try:
                new_devs = self.manager.discover_and_add_devices(timeout=3.0)
                all_devs = self.manager.list_devices()
                return jsonify({
                    'success': True,
                    'new_count': len(new_devs),
                    'devices': [d.to_dict() for d in all_devs]
                })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/devices/<device_ip>/status')
        def api_device_status(device_ip):
            try:
                board = ESPBoard(ip=device_ip, timeout=3.0)
                status = board.status()
                board.close()
                status['connected'] = True
                return jsonify(status)
            except Exception as e:
                return jsonify({'connected': False, 'error': str(e)}), 200

        @self.app.route('/api/devices/<device_ip>/capabilities')
        def api_device_capabilities(device_ip):
            try:
                board = ESPBoard(ip=device_ip, timeout=3.0)
                caps = board.capabilities()
                board.close()
                return jsonify(caps)
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/devices/<device_ip>/gpio', methods=['POST'])
        def api_gpio_control(device_ip):
            try:
                data = request.json or {}
                action = data.get('action')
                pin = data.get('pin')
                value = data.get('value')
                mode = data.get('mode')

                board = ESPBoard(ip=device_ip, timeout=3.0)

                result = {'success': True}
                if action == 'mode':
                    board.set_mode(pin, mode)
                    result['mode'] = mode
                elif action == 'write':
                    board.write(pin, int(value))
                    result['value'] = int(value)
                elif action == 'read':
                    val = board.read(pin)
                    result['value'] = val
                elif action == 'pwm':
                    board.pwm(pin, int(value))
                    result['value'] = int(value)
                elif action == 'servo':
                    board.servo(pin, int(value))
                    result['value'] = int(value)
                elif action == 'read_analog':
                    val = board.read('A0')
                    result['raw'] = val
                    result['voltage'] = round((val / 1024.0) * 3.3, 2)

                board.close()
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/devices/<device_ip>/i2c/scan', methods=['POST', 'GET'])
        def api_i2c_scan(device_ip):
            try:
                board = ESPBoard(ip=device_ip, timeout=4.0)
                addrs = board.i2c_scan()
                board.close()
                return jsonify({'success': True, 'addresses': addrs})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/devices/<device_ip>/i2c/read')
        def api_i2c_read(device_ip):
            try:
                addr = int(request.args.get('address', '0'), 0)
                length = int(request.args.get('length', '1'))
                reg = request.args.get('register')
                reg_int = int(reg, 0) if reg is not None else None

                board = ESPBoard(ip=device_ip, timeout=3.0)
                data = board.i2c_read(addr, length, register=reg_int)
                board.close()
                return jsonify({'success': True, 'data': data})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/devices/<device_ip>/i2c/write', methods=['POST'])
        def api_i2c_write(device_ip):
            try:
                data = request.json or {}
                addr = int(data.get('address', 0))
                bytes_list = data.get('data', [])

                board = ESPBoard(ip=device_ip, timeout=3.0)
                res = board.i2c_write(addr, bytes_list)
                board.close()
                return jsonify({'success': True, 'result': res})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/devices/<device_ip>/i2c/sensor/<sensor_name>')
        def api_i2c_sensor(device_ip, sensor_name):
            try:
                board = ESPBoard(ip=device_ip, timeout=3.0)
                if sensor_name.lower() == 'mpu6050':
                    res = board.read_mpu6050()
                elif sensor_name.lower() == 'bmp280':
                    res = board.read_bmp280()
                else:
                    board.close()
                    return jsonify({'error': 'Unsupported sensor'}), 400
                board.close()
                return jsonify({'success': True, 'telemetry': res})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/devices/<device_ip>/ota', methods=['POST'])
        def api_ota(device_ip):
            try:
                board = ESPBoard(ip=device_ip, timeout=60.0)

                # Check if file uploaded
                if 'file' in request.files and request.files['file'].filename:
                    uploaded = request.files['file']
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tmp:
                        uploaded.save(tmp.name)
                        tmp_path = tmp.name
                    try:
                        ok = board.ota_flash(tmp_path)
                        return jsonify({'success': ok, 'message': 'Firmware flashed successfully. Board rebooting.'})
                    finally:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                elif request.json and request.json.get('bundled'):
                    # Flash official bundled binary based on architecture
                    status = board.status()
                    arch = status.get('arch', board.architecture)
                    pkg_dir = os.path.dirname(os.path.abspath(__file__))
                    bin_name = "esp-linker-esp32.bin" if arch == "ESP32" else "esp-linker-esp8266.bin"
                    firmware_path = os.path.join(pkg_dir, "firmware", bin_name)
                    if not os.path.exists(firmware_path):
                        firmware_path = os.path.join(pkg_dir, "firmware", "esp-linker-firmware.bin")

                    ok = board.ota_flash(firmware_path)
                    return jsonify({'success': ok, 'message': f'Bundled {arch} firmware flashed. Board rebooting.'})
                else:
                    return jsonify({'success': False, 'error': 'No firmware binary provided'}), 400
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/devices/<device_ip>/reboot', methods=['POST'])
        def api_reboot(device_ip):
            try:
                import requests
                requests.post(f"http://{device_ip}/api/restart", timeout=2.0)
                return jsonify({'success': True, 'message': 'Reboot command sent'})
            except Exception:
                # Board disconnects on immediate reboot which is normal
                return jsonify({'success': True, 'message': 'Board rebooting'})

        @self.app.route('/api/devices/<device_ip>/events')
        def api_events_stream(device_ip):
            def generate():
                import requests
                try:
                    r = requests.get(f"http://{device_ip}/api/events", stream=True, timeout=60.0)
                    for line in r.iter_lines():
                        if line:
                            yield f"{line.decode('utf-8')}\n\n"
                except Exception as ex:
                    yield f"event: error\ndata: {json.dumps({'error': str(ex)})}\n\n"

            return Response(generate(), mimetype='text/event-stream')

        return self.app

    def run(self, debug: bool = False, open_browser: bool = True):
        """Run the dashboard server"""
        if not self.app:
            self.create_app()

        if open_browser:
            def open_browser_delayed():
                time.sleep(0.8)
                webbrowser.open(f'http://{self.host}:{self.port}')

            threading.Thread(target=open_browser_delayed, daemon=True).start()

        print(f"[*] ESP-Linker Web Dashboard online at http://{self.host}:{self.port}")
        print("[*] Press Ctrl+C to terminate.")

        try:
            self.app.run(host=self.host, port=self.port, debug=debug)
        except KeyboardInterrupt:
            print("\n[!] Dashboard server stopped.")


# Modern Dark Glassmorphism Frontend (Zero Emojis, Complete Responsiveness, SVG Icons)
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESP-Linker // Hardware Control Matrix</title>
    <style>
        :root {
            --bg-base: #070a13;
            --bg-surface: rgba(15, 23, 42, 0.75);
            --bg-surface-hover: rgba(30, 41, 59, 0.85);
            --bg-card: rgba(17, 24, 39, 0.9);
            --border-subtle: rgba(255, 255, 255, 0.08);
            --border-focus: rgba(6, 182, 212, 0.5);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --text-dim: #64748b;
            --cyan: #06b6d4;
            --cyan-glow: rgba(6, 182, 212, 0.25);
            --emerald: #10b981;
            --emerald-glow: rgba(16, 185, 129, 0.2);
            --indigo: #6366f1;
            --amber: #f59e0b;
            --rose: #f43f5e;
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 16px;
            --shadow-card: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-base);
            background-image: 
                radial-gradient(at 0% 0%, rgba(6, 182, 212, 0.06) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(99, 102, 241, 0.06) 0px, transparent 50%);
            background-attachment: fixed;
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }

        header {
            background: rgba(10, 15, 29, 0.85);
            backdrop-filter: blur(16px);
            border-bottom: 1px solid var(--border-subtle);
            padding: 12px 24px;
            position: sticky;
            top: 0;
            z-index: 50;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            flex-wrap: wrap;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: inherit;
        }

        .brand-icon {
            width: 34px;
            height: 34px;
            background: linear-gradient(135deg, #0284c7, #06b6d4);
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 15px var(--cyan-glow);
        }

        .brand-icon svg {
            width: 20px;
            height: 20px;
            fill: #ffffff;
        }

        .brand-title {
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .brand-tag {
            font-size: 10px;
            font-weight: 600;
            padding: 2px 6px;
            background: rgba(6, 182, 212, 0.15);
            color: var(--cyan);
            border-radius: 4px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }

        .conn-controls {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }

        .input-group {
            position: relative;
            display: flex;
            align-items: center;
        }

        .input-ip {
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid var(--border-subtle);
            color: var(--text-main);
            padding: 8px 12px;
            border-radius: var(--radius-sm);
            font-size: 13px;
            font-family: ui-monospace, SFMono-Regular, monospace;
            width: 170px;
            transition: all 0.2s ease;
        }

        .input-ip:focus {
            outline: none;
            border-color: var(--cyan);
            box-shadow: 0 0 0 2px var(--cyan-glow);
        }

        .btn {
            background: rgba(30, 41, 59, 0.8);
            color: var(--text-main);
            border: 1px solid var(--border-subtle);
            padding: 8px 14px;
            border-radius: var(--radius-sm);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.15s ease;
        }

        .btn:hover {
            background: var(--bg-surface-hover);
            border-color: rgba(255, 255, 255, 0.2);
        }

        .btn-primary {
            background: var(--cyan);
            color: #041019;
            border-color: var(--cyan);
        }

        .btn-primary:hover {
            background: #22d3ee;
            box-shadow: 0 0 12px var(--cyan-glow);
        }

        .btn-danger {
            background: rgba(244, 63, 94, 0.15);
            color: #fb7185;
            border-color: rgba(244, 63, 94, 0.3);
        }

        .btn-danger:hover {
            background: rgba(244, 63, 94, 0.25);
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid var(--border-subtle);
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--text-dim);
            transition: all 0.3s;
        }

        .status-badge.connected .pulse-dot {
            background: var(--emerald);
            box-shadow: 0 0 8px var(--emerald);
        }

        .status-badge.disconnected .pulse-dot {
            background: var(--rose);
        }

        /* Navigation Tabs */
        .nav-tabs {
            background: rgba(10, 15, 29, 0.6);
            border-bottom: 1px solid var(--border-subtle);
            display: flex;
            padding: 0 24px;
            gap: 4px;
            overflow-x: auto;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 12px 16px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
            white-space: nowrap;
        }

        .tab-btn:hover {
            color: var(--text-main);
        }

        .tab-btn.active {
            color: var(--cyan);
            border-bottom-color: var(--cyan);
        }

        .tab-btn svg {
            width: 16px;
            height: 16px;
            fill: currentColor;
        }

        /* Layout Container */
        main {
            flex: 1;
            padding: 24px;
            max-width: 1440px;
            margin: 0 auto;
            width: 100%;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
            animation: fadeIn 0.2s ease-in-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Metric Grid */
        .grid-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .card {
            background: var(--bg-surface);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 20px;
            box-shadow: var(--shadow-card);
            transition: all 0.2s ease;
        }

        .card:hover {
            border-color: rgba(255, 255, 255, 0.12);
            background: var(--bg-surface-hover);
        }

        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .card-header svg {
            width: 16px;
            height: 16px;
            fill: var(--text-dim);
        }

        .card-value {
            font-size: 26px;
            font-weight: 700;
            color: var(--text-main);
            display: flex;
            align-items: baseline;
            gap: 6px;
        }

        .card-unit {
            font-size: 13px;
            font-weight: 500;
            color: var(--text-muted);
        }

        .card-subtext {
            font-size: 12px;
            color: var(--text-dim);
            margin-top: 6px;
        }

        .progress-bar-bg {
            height: 6px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 999px;
            overflow: hidden;
            margin-top: 10px;
        }

        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--cyan), #38bdf8);
            width: 0%;
            transition: width 0.3s ease;
        }

        /* Section Panel */
        .section-panel {
            background: var(--bg-surface);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 24px;
            margin-bottom: 24px;
        }

        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 12px;
        }

        .section-title {
            font-size: 16px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .section-title svg {
            width: 18px;
            height: 18px;
            fill: var(--cyan);
        }

        /* GPIO Matrix Grid */
        .gpio-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 16px;
        }

        .pin-card {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-sm);
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            transition: all 0.2s ease;
        }

        .pin-card:hover {
            border-color: rgba(6, 182, 212, 0.3);
            background: rgba(20, 30, 55, 0.7);
        }

        .pin-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .pin-badge {
            font-size: 14px;
            font-weight: 700;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .pin-role {
            font-size: 11px;
            color: var(--text-dim);
            font-weight: 500;
        }

        .mode-select {
            background: rgba(10, 15, 29, 0.9);
            border: 1px solid var(--border-subtle);
            color: var(--text-main);
            font-size: 11px;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
        }

        .mode-select:focus {
            outline: none;
            border-color: var(--cyan);
        }

        .pin-control-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            min-height: 38px;
        }

        /* Switch Toggle */
        .toggle-switch {
            position: relative;
            display: inline-block;
            width: 44px;
            height: 24px;
        }

        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: rgba(255, 255, 255, 0.1);
            transition: .2s;
            border-radius: 24px;
        }

        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .2s;
            border-radius: 50%;
        }

        input:checked + .slider {
            background-color: var(--emerald);
        }

        input:checked + .slider:before {
            transform: translateX(20px);
        }

        /* Custom Range Slider */
        .range-slider {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 999px;
            outline: none;
            -webkit-appearance: none;
        }

        .range-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: var(--cyan);
            cursor: pointer;
            box-shadow: 0 0 8px var(--cyan-glow);
        }

        /* I2C Hex Matrix */
        .i2c-matrix-wrap {
            overflow-x: auto;
            margin-top: 16px;
        }

        .i2c-table {
            border-collapse: collapse;
            font-family: ui-monospace, SFMono-Regular, monospace;
            font-size: 13px;
            width: 100%;
            max-width: 800px;
        }

        .i2c-table th, .i2c-table td {
            border: 1px solid var(--border-subtle);
            padding: 8px 10px;
            text-align: center;
        }

        .i2c-table th {
            background: rgba(10, 15, 29, 0.8);
            color: var(--cyan);
            font-weight: 600;
        }

        .i2c-row-label {
            color: var(--cyan);
            font-weight: 600;
            background: rgba(10, 15, 29, 0.8);
        }

        .i2c-cell {
            color: var(--text-dim);
            transition: all 0.2s;
        }

        .i2c-cell.active-device {
            background: rgba(6, 182, 212, 0.2);
            color: #22d3ee;
            font-weight: 700;
            box-shadow: inset 0 0 10px rgba(6, 182, 212, 0.3);
        }

        /* Event Terminal Log */
        .log-terminal {
            background: #030712;
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-sm);
            padding: 16px;
            font-family: ui-monospace, SFMono-Regular, monospace;
            font-size: 12px;
            height: 380px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .log-line {
            display: flex;
            align-items: baseline;
            gap: 12px;
            padding: 2px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.02);
        }

        .log-ts {
            color: var(--text-dim);
        }

        .log-tag {
            font-weight: 700;
            padding: 1px 4px;
            border-radius: 3px;
            font-size: 10px;
        }

        .log-tag-event { background: rgba(6, 182, 212, 0.2); color: var(--cyan); }
        .log-tag-state-high { background: rgba(16, 185, 129, 0.2); color: var(--emerald); }
        .log-tag-state-low { background: rgba(244, 63, 94, 0.2); color: var(--rose); }

        /* OTA Drop Zone */
        .ota-dropzone {
            border: 2px dashed rgba(6, 182, 212, 0.3);
            border-radius: var(--radius-md);
            padding: 40px 20px;
            text-align: center;
            background: rgba(6, 182, 212, 0.02);
            cursor: pointer;
            transition: all 0.2s;
        }

        .ota-dropzone:hover {
            border-color: var(--cyan);
            background: rgba(6, 182, 212, 0.05);
        }

        .ota-dropzone svg {
            width: 44px;
            height: 44px;
            fill: var(--cyan);
            margin-bottom: 12px;
        }

        /* Notifications */
        .toast-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .toast {
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-subtle);
            color: var(--text-main);
            padding: 12px 18px;
            border-radius: var(--radius-sm);
            font-size: 13px;
            font-weight: 500;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            gap: 10px;
            animation: slideIn 0.2s ease-out;
        }

        @keyframes slideIn {
            from { transform: translateX(50px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .toast.success { border-left: 4px solid var(--emerald); }
        .toast.error { border-left: 4px solid var(--rose); }
        .toast.info { border-left: 4px solid var(--cyan); }

        /* Responsive */
        @media (max-width: 768px) {
            header {
                padding: 12px 16px;
            }
            .input-ip {
                width: 140px;
            }
            main {
                padding: 16px;
            }
        }
    </style>
</head>
<body>

    <header>
        <a href="#" class="brand">
            <div class="brand-icon">
                <svg viewBox="0 0 24 24"><path d="M4 6h16v12H4V6zm2 2v8h12V8H6zm2 2h3v4H8v-4zm5 0h3v4h-3v-4zM2 4h20v16H2V4z"/></svg>
            </div>
            <div>
                <div class="brand-title">ESP-LINKER <span class="brand-tag">v1.4.0</span></div>
            </div>
        </a>

        <div class="conn-controls">
            <div class="input-group">
                <input type="text" id="targetIpInput" class="input-ip" placeholder="Target IP (e.g. 192.168.1.50)">
            </div>
            <button class="btn btn-primary" id="btnConnect" onclick="connectTarget()">Connect</button>
            <button class="btn" id="btnDiscover" onclick="discoverDevices()">Scan Network</button>
            
            <div id="connBadge" class="status-badge disconnected">
                <div class="pulse-dot"></div>
                <span id="connLabel">Disconnected</span>
            </div>
        </div>
    </header>

    <nav class="nav-tabs">
        <button class="tab-btn active" onclick="switchTab('overview')">
            <svg viewBox="0 0 24 24"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>
            Overview & Telemetry
        </button>
        <button class="tab-btn" onclick="switchTab('gpio')">
            <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9v-2h2v2zm0-4H9V7h2v5zm4 4h-2v-2h2v2zm0-4h-2V7h2v5z"/></svg>
            GPIO Matrix
        </button>
        <button class="tab-btn" onclick="switchTab('i2c')">
            <svg viewBox="0 0 24 24"><path d="M4 4h16v4H4V4zm0 6h16v4H4v-4zm0 6h16v4H4v-4z"/></svg>
            I2C Bus & Sensors
        </button>
        <button class="tab-btn" onclick="switchTab('ota')">
            <svg viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
            OTA Flasher
        </button>
        <button class="tab-btn" onclick="switchTab('events')">
            <svg viewBox="0 0 24 24"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-5 14H4v-4h11v4zm0-5H4V9h11v4zm5 5h-4V9h4v9z"/></svg>
            Interrupt Events
        </button>
    </nav>

    <main>
        <!-- 1. OVERVIEW TAB -->
        <div id="tab-overview" class="tab-content active">
            <div class="grid-cards">
                <div class="card">
                    <div class="card-header">
                        <span>Architecture & Target</span>
                        <svg viewBox="0 0 24 24"><path d="M4 6h16v12H4V6zm2 2v8h12V8H6z"/></svg>
                    </div>
                    <div class="card-value" id="cardArch">---</div>
                    <div class="card-subtext" id="cardFirmware">ESP-Linker Firmware</div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span>Free Heap Memory</span>
                        <svg viewBox="0 0 24 24"><path d="M2 9h20v6H2V9zm2 2v2h16v-2H4z"/></svg>
                    </div>
                    <div class="card-value" id="cardHeap">--- <span class="card-unit">KB</span></div>
                    <div class="progress-bar-bg">
                        <div id="heapProgress" class="progress-bar-fill" style="width: 50%;"></div>
                    </div>
                    <div class="card-subtext" id="cardHeapExact">Awaiting connection</div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span>WiFi Signal (RSSI)</span>
                        <svg viewBox="0 0 24 24"><path d="M12 4C7.31 4 3.07 5.9 0 8.98L12 21 24 8.98C20.93 5.9 16.69 4 12 4zm0 3.32c3.81 0 7.28 1.48 9.87 3.91L12 19.1 2.13 11.23C4.72 8.8 8.19 7.32 12 7.32z"/></svg>
                    </div>
                    <div class="card-value" id="cardRssi">--- <span class="card-unit">dBm</span></div>
                    <div class="card-subtext" id="cardSsid">SSID: ---</div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span>Board Uptime</span>
                        <svg viewBox="0 0 24 24"><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.2 3.2.8-1.3-4.5-2.7V7z"/></svg>
                    </div>
                    <div class="card-value" id="cardUptime">---</div>
                    <div class="card-subtext" id="cardChipId">Chip ID: ---</div>
                </div>
            </div>

            <div class="section-panel">
                <div class="section-header">
                    <div class="section-title">
                        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
                        Quick Board Actions
                    </div>
                </div>
                <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                    <button class="btn" onclick="fetchStatus()">Refresh Status</button>
                    <button class="btn" onclick="rebootBoard()">Soft Reboot</button>
                </div>
            </div>
        </div>

        <!-- 2. GPIO MATRIX TAB -->
        <div id="tab-gpio" class="tab-content">
            <div class="section-panel">
                <div class="section-header">
                    <div class="section-title">
                        <svg viewBox="0 0 24 24"><path d="M4 6h16v12H4V6zm2 2v8h12V8H6z"/></svg>
                        Digital & Analog Pin Matrix
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button class="btn" onclick="fetchCapabilities()">Reload Pins</button>
                    </div>
                </div>

                <div id="gpioContainer" class="gpio-grid">
                    <div style="color: var(--text-dim); padding: 20px;">Connect to an ESP board to load active pin grid.</div>
                </div>
            </div>

            <div class="section-panel">
                <div class="section-header">
                    <div class="section-title">
                        <svg viewBox="0 0 24 24"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg>
                        ADC Analog Channel (A0)
                    </div>
                    <button class="btn" onclick="pollAdc()">Sample ADC</button>
                </div>
                <div style="display: flex; align-items: baseline; gap: 20px;">
                    <div>
                        <div style="font-size: 32px; font-weight: 700;" id="ad城市oltage">0.00 V</div>
                        <div style="color: var(--text-dim); font-size: 13px;" id="adcRaw">Raw: 0 / 1024</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 3. I2C BUS & SENSORS TAB -->
        <div id="tab-i2c" class="tab-content">
            <div class="section-panel">
                <div class="section-header">
                    <div class="section-title">
                        <svg viewBox="0 0 24 24"><path d="M4 4h16v4H4V4zm0 6h16v4H4v-4zm0 6h16v4H4v-4z"/></svg>
                        I2C Hardware Bus Map (0x00 - 0x7F)
                    </div>
                    <button class="btn btn-primary" onclick="scanI2C()">Scan I2C Bus</button>
                </div>

                <div class="i2c-matrix-wrap">
                    <table class="i2c-table" id="i2cTable">
                        <!-- Populated dynamically -->
                    </table>
                </div>
                <div style="margin-top: 16px; font-size: 13px; color: var(--text-muted);" id="i2cSummary">
                    Click "Scan I2C Bus" to detect connected peripherals.
                </div>
            </div>

            <div class="grid-cards">
                <div class="card">
                    <div class="card-header">
                        <span>MPU-6050 Motion Sensor (0x68)</span>
                        <button class="btn" style="padding: 4px 8px; font-size: 11px;" onclick="pollSensor('mpu6050')">Read</button>
                    </div>
                    <div style="font-family: ui-monospace, monospace; font-size: 13px; line-height: 1.8;" id="mpuTelemetry">
                        Accel: X: 0.000g, Y: 0.000g, Z: 0.000g<br>
                        Gyro: X: 0.00 d/s, Y: 0.00 d/s, Z: 0.00 d/s<br>
                        Temperature: -- °C
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span>BMP280 Barometer (0x76 / 0x77)</span>
                        <button class="btn" style="padding: 4px 8px; font-size: 11px;" onclick="pollSensor('bmp280')">Detect</button>
                    </div>
                    <div style="font-family: ui-monospace, monospace; font-size: 13px; line-height: 1.8;" id="bmpTelemetry">
                        Sensor: Awaiting query<br>
                        Chip ID: --<br>
                        Address: --
                    </div>
                </div>
            </div>
        </div>

        <!-- 4. OTA FLASHER TAB -->
        <div id="tab-ota" class="tab-content">
            <div class="section-panel">
                <div class="section-header">
                    <div class="section-title">
                        <svg viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
                        Wireless Over-The-Air (OTA) Firmware Flasher
                    </div>
                </div>

                <div class="ota-dropzone" onclick="document.getElementById('otaFileInput').click()">
                    <svg viewBox="0 0 24 24"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>
                    <div style="font-size: 15px; font-weight: 600;">Choose or Drop Firmware Binary (.bin)</div>
                    <div style="color: var(--text-dim); font-size: 12px; margin-top: 6px;">Target architecture will be validated automatically</div>
                    <input type="file" id="otaFileInput" style="display: none;" accept=".bin" onchange="handleFileSelected(this)">
                </div>

                <div id="otaFileSelected" style="margin-top: 14px; font-size: 13px; color: var(--cyan); display: none;"></div>

                <div style="margin-top: 20px; display: flex; gap: 12px; flex-wrap: wrap;">
                    <button class="btn btn-primary" id="btnUploadOta" onclick="uploadOtaFile()" disabled>Flash Uploaded Binary</button>
                    <button class="btn" onclick="flashBundledOta()">Flash Bundled Official Firmware</button>
                </div>

                <div id="otaProgressContainer" style="margin-top: 20px; display: none;">
                    <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
                        <span id="otaStatusText">Uploading firmware binary...</span>
                        <span id="otaPercentText">0%</span>
                    </div>
                    <div class="progress-bar-bg" style="height: 10px;">
                        <div id="otaProgressBar" class="progress-bar-fill" style="width: 0%;"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 5. INTERRUPT EVENTS TAB -->
        <div id="tab-events" class="tab-content">
            <div class="section-panel">
                <div class="section-header">
                    <div class="section-title">
                        <svg viewBox="0 0 24 24"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-5 14H4v-4h11v4zm0-5H4V9h11v4zm5 5h-4V9h4v9z"/></svg>
                        Live GPIO Interrupt Event Stream
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button class="btn" onclick="clearEventLog()">Clear Log</button>
                        <button class="btn btn-primary" id="btnToggleEvents" onclick="toggleEventStream()">Connect SSE</button>
                    </div>
                </div>

                <div class="log-terminal" id="eventLogContainer">
                    <div class="log-line">
                        <span class="log-ts">[00:00:00]</span>
                        <span class="log-tag log-tag-event">READY</span>
                        <span style="color: var(--text-dim);">Awaiting Server-Sent Events stream initialization.</span>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <div class="toast-container" id="toastContainer"></div>

    <script>
        let currentIp = "";
        let eventSource = null;
        let activeTab = "overview";
        let knownPins = [];

        // Tab Switching
        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            const btn = document.querySelector(`.tab-btn[onclick*="${tabId}"]`);
            if (btn) btn.classList.add('active');
            
            const target = document.getElementById(`tab-${tabId}`);
            if (target) target.classList.add('active');
            activeTab = tabId;

            if (tabId === 'gpio' && knownPins.length === 0 && currentIp) {
                fetchCapabilities();
            }
        }

        // Notification Toasts
        function toast(msg, type = "info") {
            const container = document.getElementById('toastContainer');
            const el = document.createElement('div');
            el.className = `toast ${type}`;
            el.textContent = msg;
            container.appendChild(el);
            setTimeout(() => {
                el.style.opacity = '0';
                el.style.transform = 'translateY(10px)';
                el.style.transition = 'all 0.2s';
                setTimeout(() => el.remove(), 200);
            }, 3000);
        }

        // Connect Target
        async function connectTarget() {
            const ipInput = document.getElementById('targetIpInput').value.trim();
            if (!ipInput) {
                toast("Please enter an ESP IP address", "error");
                return;
            }
            currentIp = ipInput;
            toast(`Connecting to ${currentIp}...`, "info");
            await fetchStatus();
            await fetchCapabilities();
        }

        // Discover Devices
        async function discoverDevices() {
            toast("Scanning local network for ESP-Linker devices...", "info");
            try {
                const res = await fetch('/api/devices/discover', { method: 'POST' });
                const data = await res.json();
                if (data.devices && data.devices.length > 0) {
                    toast(`Found ${data.devices.length} ESP-Linker device(s)`, "success");
                    document.getElementById('targetIpInput').value = data.devices[0].ip;
                    currentIp = data.devices[0].ip;
                    fetchStatus();
                } else {
                    toast("No ESP-Linker devices found on network", "info");
                }
            } catch (err) {
                toast(`Discovery error: ${err.message}`, "error");
            }
        }

        // Fetch Telemetry & Status
        async function fetchStatus() {
            if (!currentIp) return;
            try {
                const res = await fetch(`/api/devices/${currentIp}/status`);
                const data = await res.json();
                const badge = document.getElementById('connBadge');
                const label = document.getElementById('connLabel');

                if (data.connected !== false) {
                    badge.className = "status-badge connected";
                    label.textContent = `${currentIp} (${data.arch || 'ESP'})`;

                    document.getElementById('cardArch').textContent = data.arch || 'ESP8266';
                    document.getElementById('cardFirmware').textContent = `${data.firmware_name || 'ESP-Linker'} v${data.firmware_version || '1.0'}`;
                    
                    const freeKb = Math.round((data.free_heap || 0) / 1024);
                    document.getElementById('cardHeap').innerHTML = `${freeKb} <span class="card-unit">KB</span>`;
                    document.getElementById('cardHeapExact').textContent = `${(data.free_heap || 0).toLocaleString()} bytes available`;
                    
                    const heapPct = Math.min(100, Math.max(10, Math.round((data.free_heap / 80000) * 100)));
                    document.getElementById('heapProgress').style.width = `${heapPct}%`;

                    document.getElementById('cardRssi').innerHTML = `${data.wifi_rssi || '--'} <span class="card-unit">dBm</span>`;
                    document.getElementById('cardSsid').textContent = `SSID: ${data.wifi_ssid || 'AP Mode'}`;

                    const sec = data.uptime || 0;
                    const h = Math.floor(sec / 3600);
                    const m = Math.floor((sec % 3600) / 60);
                    const s = sec % 60;
                    document.getElementById('cardUptime').textContent = `${h}h ${m}m ${s}s`;
                    document.getElementById('cardChipId').textContent = `Chip ID: ${data.chip_id || '--'}`;
                } else {
                    badge.className = "status-badge disconnected";
                    label.textContent = "Offline";
                    toast(`Unable to connect to ${currentIp}: ${data.error}`, "error");
                }
            } catch (e) {
                document.getElementById('connBadge').className = "status-badge disconnected";
                document.getElementById('connLabel').textContent = "Error";
                toast(`Connection error: ${e.message}`, "error");
            }
        }

        // Fetch Capabilities & Render Pins
        async function fetchCapabilities() {
            if (!currentIp) return;
            try {
                const res = await fetch(`/api/devices/${currentIp}/capabilities`);
                const data = await res.json();
                const container = document.getElementById('gpioContainer');
                container.innerHTML = "";

                knownPins = data.pins || [];
                if (knownPins.length === 0) {
                    container.innerHTML = `<div style="color: var(--text-dim);">No GPIO capabilities returned by device.</div>`;
                    return;
                }

                knownPins.forEach(p => {
                    const card = document.createElement('div');
                    card.className = "pin-card";
                    card.id = `pinCard-${p.pin}`;

                    let modesHtml = `<option value="INPUT">INPUT</option><option value="OUTPUT" selected>OUTPUT</option>`;
                    if (p.pwm) modesHtml += `<option value="PWM">PWM</option>`;
                    if (p.servo) modesHtml += `<option value="SERVO">SERVO</option>`;

                    card.innerHTML = `
                        <div class="pin-header">
                            <div class="pin-badge">
                                <span>GPIO ${p.pin}</span>
                                <span class="pin-role">${p.label || ''}</span>
                            </div>
                            <select class="mode-select" onchange="setPinMode(${p.pin}, this.value)">
                                ${modesHtml}
                            </select>
                        </div>
                        <div class="pin-control-row" id="pinControlRow-${p.pin}">
                            <span style="font-size: 12px; color: var(--text-muted);">State</span>
                            <label class="toggle-switch">
                                <input type="checkbox" onchange="writePin(${p.pin}, this.checked ? 1 : 0)">
                                <span class="slider"></span>
                            </label>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch (err) {
                toast(`Failed to load pin table: ${err.message}`, "error");
            }
        }

        // Set Pin Mode
        async function setPinMode(pin, mode) {
            try {
                await fetch(`/api/devices/${currentIp}/gpio`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'mode', pin: pin, mode: mode })
                });
                toast(`GPIO ${pin} set to ${mode}`, "success");

                const row = document.getElementById(`pinControlRow-${pin}`);
                if (mode === 'OUTPUT') {
                    row.innerHTML = `
                        <span style="font-size: 12px; color: var(--text-muted);">Output</span>
                        <label class="toggle-switch">
                            <input type="checkbox" onchange="writePin(${pin}, this.checked ? 1 : 0)">
                            <span class="slider"></span>
                        </label>
                    `;
                } else if (mode === 'INPUT') {
                    row.innerHTML = `
                        <span style="font-size: 12px; color: var(--text-muted);">Input Level</span>
                        <button class="btn" style="padding: 2px 8px; font-size: 11px;" onclick="readPin(${pin})">Read</button>
                    `;
                } else if (mode === 'PWM') {
                    row.innerHTML = `
                        <div style="width: 100%;">
                            <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px;">
                                <span>Duty</span><span id="pwmVal-${pin}">0</span>
                            </div>
                            <input type="range" class="range-slider" min="0" max="1023" value="0" oninput="document.getElementById('pwmVal-${pin}').textContent=this.value" onchange="setPwmPin(${pin}, this.value)">
                        </div>
                    `;
                } else if (mode === 'SERVO') {
                    row.innerHTML = `
                        <div style="width: 100%;">
                            <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px;">
                                <span>Angle</span><span id="servoVal-${pin}">90°</span>
                            </div>
                            <input type="range" class="range-slider" min="0" max="180" value="90" oninput="document.getElementById('servoVal-${pin}').textContent=this.value+'°'" onchange="setServoPin(${pin}, this.value)">
                        </div>
                    `;
                }
            } catch (e) {
                toast(`Mode change failed: ${e.message}`, "error");
            }
        }

        // GPIO Pin Operations
        async function writePin(pin, val) {
            try {
                await fetch(`/api/devices/${currentIp}/gpio`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'write', pin: pin, value: val })
                });
            } catch (e) {
                toast(`GPIO write error: ${e.message}`, "error");
            }
        }

        async function readPin(pin) {
            try {
                const res = await fetch(`/api/devices/${currentIp}/gpio`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'read', pin: pin })
                });
                const data = await res.json();
                toast(`GPIO ${pin} state: ${data.value === 1 ? 'HIGH' : 'LOW'}`, "info");
            } catch (e) {
                toast(`GPIO read error: ${e.message}`, "error");
            }
        }

        async function setPwmPin(pin, val) {
            try {
                await fetch(`/api/devices/${currentIp}/gpio`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'pwm', pin: pin, value: parseInt(val) })
                });
            } catch (e) {
                toast(`PWM error: ${e.message}`, "error");
            }
        }

        async function setServoPin(pin, angle) {
            try {
                await fetch(`/api/devices/${currentIp}/gpio`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'servo', pin: pin, value: parseInt(angle) })
                });
            } catch (e) {
                toast(`Servo error: ${e.message}`, "error");
            }
        }

        async function pollAdc() {
            if (!currentIp) return;
            try {
                const res = await fetch(`/api/devices/${currentIp}/gpio`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'read_analog' })
                });
                const data = await res.json();
                document.getElementById('adcVoltage').textContent = `${data.voltage.toFixed(2)} V`;
                document.getElementById('adcRaw').textContent = `Raw: ${data.raw} / 1024`;
            } catch (e) {
                toast(`ADC read error: ${e.message}`, "error");
            }
        }

        // I2C Bus Scanner
        function initI2cTable() {
            const table = document.getElementById('i2cTable');
            table.innerHTML = "";
            let header = `<tr><th></th>`;
            for (let c = 0; c < 16; c++) {
                header += `<th>${c.toString(16).toUpperCase().padStart(2, '0')}</th>`;
            }
            header += `</tr>`;
            table.innerHTML += header;

            for (let r = 0; r < 8; r++) {
                const base = r * 16;
                let row = `<tr><td class="i2c-row-label">${base.toString(16).toUpperCase().padStart(2, '0')}:</td>`;
                for (let c = 0; c < 16; c++) {
                    const addr = base + c;
                    row += `<td class="i2c-cell" id="i2cCell-${addr}">--</td>`;
                }
                row += `</tr>`;
                table.innerHTML += row;
            }
        }

        async function scanI2C() {
            if (!currentIp) {
                toast("Please connect to a device first", "error");
                return;
            }
            initI2cTable();
            toast("Scanning I2C peripheral bus...", "info");
            try {
                const res = await fetch(`/api/devices/${currentIp}/i2c/scan`, { method: 'POST' });
                const data = await res.json();
                const addrs = data.addresses || [];

                document.querySelectorAll('.i2c-cell').forEach(c => {
                    c.textContent = "--";
                    c.classList.remove('active-device');
                });

                addrs.forEach(addr => {
                    const cell = document.getElementById(`i2cCell-${addr}`);
                    if (cell) {
                        cell.textContent = addr.toString(16).toUpperCase().padStart(2, '0');
                        cell.classList.add('active-device');
                    }
                });

                document.getElementById('i2cSummary').textContent = 
                    `Discovered ${addrs.length} device(s): ${addrs.map(a => '0x' + a.toString(16).toUpperCase()).join(', ') || 'None'}`;
                toast(`I2C Scan complete: ${addrs.length} device(s) found`, "success");
            } catch (e) {
                toast(`I2C scan failed: ${e.message}`, "error");
            }
        }

        async function pollSensor(sensor) {
            if (!currentIp) return;
            try {
                const res = await fetch(`/api/devices/${currentIp}/i2c/sensor/${sensor}`);
                const data = await res.json();
                if (sensor === 'mpu6050') {
                    const t = data.telemetry;
                    document.getElementById('mpuTelemetry').innerHTML = `
                        Accel: X: ${t.accel_x}g, Y: ${t.accel_y}g, Z: ${t.accel_z}g<br>
                        Gyro: X: ${t.gyro_x} d/s, Y: ${t.gyro_y} d/s, Z: ${t.gyro_z} d/s<br>
                        Temperature: ${t.temp_c} °C
                    `;
                } else if (sensor === 'bmp280') {
                    const t = data.telemetry;
                    document.getElementById('bmpTelemetry').innerHTML = `
                        Sensor Model: ${t.model}<br>
                        Chip ID: ${t.chip_id}<br>
                        Address: ${t.address}
                    `;
                }
            } catch (e) {
                toast(`Sensor read failed: ${e.message}`, "error");
            }
        }

        // OTA Flashing
        let selectedOtaFile = null;

        function handleFileSelected(input) {
            if (input.files && input.files[0]) {
                selectedOtaFile = input.files[0];
                const info = document.getElementById('otaFileSelected');
                info.style.display = 'block';
                info.textContent = `Selected: ${selectedOtaFile.name} (${(selectedOtaFile.size / 1024).toFixed(1)} KB)`;
                document.getElementById('btnUploadOta').disabled = false;
            }
        }

        async function uploadOtaFile() {
            if (!selectedOtaFile || !currentIp) return;
            const formData = new FormData();
            formData.append('file', selectedOtaFile);

            document.getElementById('otaProgressContainer').style.display = 'block';
            document.getElementById('otaProgressBar').style.width = '30%';
            document.getElementById('otaStatusText').textContent = 'Uploading firmware to board...';
            document.getElementById('btnUploadOta').disabled = true;

            try {
                const res = await fetch(`/api/devices/${currentIp}/ota`, {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (data.success) {
                    document.getElementById('otaProgressBar').style.width = '100%';
                    document.getElementById('otaStatusText').textContent = 'Flash Complete! Rebooting board...';
                    toast("Firmware flashed successfully! Board rebooting...", "success");
                } else {
                    toast(`OTA flash failed: ${data.error}`, "error");
                }
            } catch (e) {
                toast(`OTA error: ${e.message}`, "error");
            }
        }

        async function flashBundledOta() {
            if (!currentIp) {
                toast("Please connect to a device first", "error");
                return;
            }
            if (!confirm(`Flash bundled official firmware to ${currentIp}? Board will reboot upon completion.`)) return;

            document.getElementById('otaProgressContainer').style.display = 'block';
            document.getElementById('otaProgressBar').style.width = '50%';
            document.getElementById('otaStatusText').textContent = 'Installing official firmware...';

            try {
                const res = await fetch(`/api/devices/${currentIp}/ota`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ bundled: true })
                });
                const data = await res.json();
                if (data.success) {
                    document.getElementById('otaProgressBar').style.width = '100%';
                    document.getElementById('otaStatusText').textContent = 'Firmware updated! Reconnecting...';
                    toast("Official firmware installed! Board rebooting...", "success");
                    setTimeout(fetchStatus, 6000);
                } else {
                    toast(`Bundled flash failed: ${data.error}`, "error");
                }
            } catch (e) {
                toast(`Flash error: ${e.message}`, "error");
            }
        }

        // Reboot Board
        async function rebootBoard() {
            if (!currentIp) return;
            if (!confirm(`Are you sure you want to soft reboot board at ${currentIp}?`)) return;
            try {
                await fetch(`/api/devices/${currentIp}/reboot`, { method: 'POST' });
                toast("Reboot command dispatched. Board restarting...", "info");
                setTimeout(fetchStatus, 4000);
            } catch (e) {
                toast(`Reboot error: ${e.message}`, "error");
            }
        }

        // SSE Real-Time Interrupt Events
        function toggleEventStream() {
            const btn = document.getElementById('btnToggleEvents');
            if (eventSource) {
                eventSource.close();
                eventSource = null;
                btn.textContent = "Connect SSE";
                btn.className = "btn btn-primary";
                appendLog("DISCONNECTED", "Event stream closed by user.");
            } else {
                if (!currentIp) {
                    toast("Please connect to a device first", "error");
                    return;
                }
                eventSource = new EventSource(`/api/devices/${currentIp}/events`);
                btn.textContent = "Disconnect SSE";
                btn.className = "btn btn-danger";

                eventSource.onopen = () => {
                    appendLog("CONNECTED", `Live event stream open on http://${currentIp}/api/events`);
                };

                eventSource.onmessage = (e) => {
                    try {
                        const evt = JSON.parse(e.data);
                        const stateTag = evt.state === 1 ? 'log-tag-state-high' : 'log-tag-state-low';
                        appendLog(`GPIO ${evt.pin}`, `State: ${evt.state === 1 ? 'HIGH' : 'LOW'} (millis: ${evt.millis || '--'})`, stateTag);
                    } catch {
                        appendLog("RAW", e.data);
                    }
                };

                eventSource.onerror = () => {
                    appendLog("ERROR", "SSE connection dropped or lost.");
                };
            }
        }

        function appendLog(tag, message, tagClass = "log-tag-event") {
            const container = document.getElementById('eventLogContainer');
            const line = document.createElement('div');
            line.className = "log-line";
            const now = new Date().toTimeString().split(' ')[0];
            line.innerHTML = `
                <span class="log-ts">[${now}]</span>
                <span class="log-tag ${tagClass}">${tag}</span>
                <span>${message}</span>
            `;
            container.appendChild(line);
            container.scrollTop = container.scrollHeight;
        }

        function clearEventLog() {
            document.getElementById('eventLogContainer').innerHTML = "";
        }

        // Initialize on load
        window.addEventListener('DOMContentLoaded', () => {
            initI2cTable();
            // Auto-check devices
            fetch('/api/devices').then(r => r.json()).then(devs => {
                if (devs && devs.length > 0) {
                    document.getElementById('targetIpInput').value = devs[0].ip;
                    currentIp = devs[0].ip;
                    fetchStatus();
                }
            }).catch(() => {});
        });
    </script>
</body>
</html>
"""


def run_dashboard(host: str = 'localhost', port: int = 8080, debug: bool = False):
    """
    Run the ESP-Linker web dashboard.

    Args:
        host: Host to bind to
        port: Port to bind to
        debug: Enable debug mode
    """
    dashboard = Dashboard(host, port)
    dashboard.run(debug=debug)

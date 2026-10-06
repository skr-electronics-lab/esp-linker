"""
ESP-Linker Web Dashboard
(c) 2025 SK Raihan / SKR Electronics Lab

Simple web dashboard for monitoring and controlling ESP-Linker devices.
"""

import json
import threading
import webbrowser
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

try:
    from flask import Flask, render_template_string, jsonify, request
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

from .device_manager import get_device_manager
from .espboard import ESPBoard


class Dashboard:
    """Simple web dashboard for ESP-Linker devices"""
    
    def __init__(self, host: str = 'localhost', port: int = 8080):
        self.host = host
        self.port = port
        self.app = None
        self.manager = get_device_manager()
        
        if not FLASK_AVAILABLE:
            raise ImportError("Flask is required for the dashboard. Install with: pip install flask")
    
    def create_app(self):
        """Create Flask application"""
        self.app = Flask(__name__)
        
        # Main dashboard page
        @self.app.route('/')
        def dashboard():
            return render_template_string(DASHBOARD_HTML)
        
        # API endpoints
        @self.app.route('/api/devices')
        def api_devices():
            devices = self.manager.list_devices()
            return jsonify([device.to_dict() for device in devices])
        
        @self.app.route('/api/devices/discover', methods=['POST'])
        def api_discover():
            try:
                new_devices = self.manager.discover_and_add_devices()
                return jsonify({
                    'success': True,
                    'new_devices': len(new_devices),
                    'devices': [device.to_dict() for device in new_devices]
                })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/devices/<device_ip>/status')
        def api_device_status(device_ip):
            try:
                device = self.manager.get_device(device_ip)
                if not device:
                    return jsonify({'error': 'Device not found'}), 404
                
                board = ESPBoard(ip=device.ip, timeout=3)
                status = board.status()
                board.close()
                
                return jsonify(status)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/devices/<device_ip>/gpio', methods=['POST'])
        def api_gpio_control(device_ip):
            try:
                device = self.manager.get_device(device_ip)
                if not device:
                    return jsonify({'error': 'Device not found'}), 404
                
                data = request.json
                action = data.get('action')
                pin = data.get('pin')
                value = data.get('value')
                
                board = ESPBoard(ip=device.ip, timeout=3)
                
                if action == 'write':
                    board.write(pin, value)
                elif action == 'read':
                    value = board.read(pin)
                elif action == 'pwm':
                    board.pwm(pin, value)
                
                board.close()
                
                return jsonify({'success': True, 'value': value})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/statistics')
        def api_statistics():
            stats = self.manager.get_statistics()
            return jsonify(stats)
        
        return self.app
    
    def run(self, debug: bool = False, open_browser: bool = True):
        """Run the dashboard server"""
        if not self.app:
            self.create_app()
        
        if open_browser:
            # Open browser after a short delay
            def open_browser_delayed():
                import time
                time.sleep(1)
                webbrowser.open(f'http://{self.host}:{self.port}')
            
            threading.Thread(target=open_browser_delayed, daemon=True).start()
        
        print(f"[*] ESP-Linker Dashboard starting at http://{self.host}:{self.port}")
        print("Press Ctrl+C to stop the dashboard")
        
        try:
            self.app.run(host=self.host, port=self.port, debug=debug)
        except KeyboardInterrupt:
            print("\n[!] Dashboard stopped")


# HTML template for the dashboard
DASHBOARD_HTML = """
<!DOCTYPE html> 
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESP-Linker Dashboard</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #1a1a1a;
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: #2d2d2d;
            padding: 20px;
            border-radius: 8px;
        }

        h1 {
            color: #4CAF50;
            text-align: center;
            margin-bottom: 5px;
        }

        .subtitle {
            text-align: center;
            color: #aaa;
            margin-bottom: 20px;
            font-size: 14px;
        }

        .status {
            background: #333;
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 4px;
            border-left: 4px solid #4CAF50;
        }

        .status.disconnected {
            border-left-color: #f44336;
        }

        .form-group {
            margin-bottom: 15px;
        }

        button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 10px 16px;
            border-radius: 4px;
            cursor: pointer;
            margin: 4px;
        }

        button:hover {
            background: #45a049;
        }

        button.warning {
            background: #FF9800;
        }

        button.warning:hover {
            background: #F57C00;
        }

        button.danger {
            background: #f44336;
        }

        button.danger:hover {
            background: #d32f2f;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: #333;
            padding: 16px;
            border-radius: 6px;
            border-left: 4px solid #4CAF50;
            text-align: center;
        }

        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
            margin-bottom: 6px;
        }

        .stat-label {
            color: #aaa;
            font-size: 13px;
        }

        .device-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }

        .device-card {
            background: #333;
            border: 1px solid #555;
            border-radius: 6px;
            padding: 16px;
        }

        .device-name {
            color: #4CAF50;
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 10px;
        }

        .device-info {
            color: #ccc;
            margin-bottom: 10px;
            font-size: 14px;
        }

        .device-status {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            margin-bottom: 10px;
        }

        .status-online {
            background: #2e7d32;
            color: white;
        }

        .status-offline {
            background: #c62828;
            color: white;
        }

        .error {
            background: #c62828;
            color: white;
            padding: 12px;
            border-radius: 6px;
            text-align: center;
        }

        .loading {
            text-align: center;
            padding: 20px;
            color: #aaa;
        }

        .section h2 {
            color: #4CAF50;
            font-size: 18px;
            margin-bottom: 12px;
        }

        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 14px 18px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 1000;
            max-width: 400px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
            transform: translateX(100%);
            transition: transform 0.3s ease;
        }

        .notification-success { background: #2e7d32; }
        .notification-error { background: #c62828; }
        .notification-info { background: #1976d2; }
        .notification-warning { background: #ed6c02; }

        @media (max-width: 600px) {
            .device-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>ESP-Linker Dashboard</h1>
        <div class="subtitle">Device Management & Control</div>

        <div class="status" id="connectionStatus">
            <strong>Status:</strong> <span id="statusText">Loading...</span>
        </div>

        <!-- Statistics Section -->
        <div class="section">
            <h2>System Statistics</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="total-devices">0</div>
                    <div class="stat-label">Total Devices</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="online-devices">0</div>
                    <div class="stat-label">Online Devices</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="offline-devices">0</div>
                    <div class="stat-label">Offline Devices</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="last-scan">Never</div>
                    <div class="stat-label">Last Scan</div>
                </div>
            </div>
        </div>

        <!-- Global Controls -->
        <div class="section">
            <h2>Global Controls</h2>
            <div class="form-group">
                <button onclick="discoverDevices()">Discover Devices</button>
                <button onclick="refreshAll()">Refresh All</button>
                <button onclick="exportConfig()" class="warning">Export Config</button>
            </div>
        </div>

        <!-- Connected Devices -->
        <div class="section">
            <h2>Connected Devices</h2>
            <div id="devices" class="device-grid">
                <div class="loading">Scanning for devices...</div>
            </div>
        </div>

    </div> <!-- Close container -->
    
    <script>
        let devices = [];

        async function loadStatistics() {
            try {
                const response = await fetch('/api/statistics');
                const stats = await response.json();

                // Update statistics cards
                document.getElementById('total-devices').textContent = stats.total_devices || 0;
                document.getElementById('online-devices').textContent = stats.online_devices || 0;
                document.getElementById('offline-devices').textContent = stats.offline_devices || 0;
                document.getElementById('last-scan').textContent = stats.last_discovery || 'Never';

                // Update status
                const statusText = document.getElementById('statusText');
                const connectionStatus = document.getElementById('connectionStatus');
                if (stats.online_devices > 0) {
                    statusText.textContent = `${stats.online_devices} device(s) online`;
                    connectionStatus.classList.remove('disconnected');
                } else {
                    statusText.textContent = 'No devices online';
                    connectionStatus.classList.add('disconnected');
                }
            } catch (error) {
                console.error('Error loading statistics:', error);
                document.getElementById('statusText').textContent = 'Failed to load statistics';
                document.getElementById('connectionStatus').classList.add('disconnected');
            }
        }

        async function loadDevices() {
            try {
                const response = await fetch('/api/devices');
                devices = await response.json();

                if (devices.length === 0) {
                    document.getElementById('devices').innerHTML = `
                        <div class="loading">
                            <i class="fas fa-search"></i>
                            <div>No devices found. Click "Discover Devices" to scan your network.</div>
                        </div>
                    `;
                    return;
                }

                const devicesHtml = devices.map(device => `
                    <div class="device-card">
                        <div class="device-name">${device.name}</div>
                        <div class="device-info">
                            IP: ${device.ip}<br>
                            Firmware: ${device.firmware_name} v${device.firmware_version}<br>
                            Last Seen: ${new Date(device.last_seen).toLocaleString()}<br>
                            Memory: ${device.free_memory || 'N/A'} KB free
                        </div>
                        <div class="device-status status-${device.status}">
                            ${device.status.toUpperCase()}
                        </div>
                        <div class="form-group">
                            <button onclick="toggleLED('${device.ip}')">LED Toggle</button>
                            <button onclick="testPWM('${device.ip}')">PWM Test</button>
                            <button onclick="getStatus('${device.ip}')">Status</button>
                            <button onclick="readAnalog('${device.ip}')">Read A0</button>
                            <button onclick="restartDevice('${device.ip}')" class="warning">Restart</button>
                            <button onclick="factoryReset('${device.ip}')" class="danger">Reset</button>
                        </div>
                    </div>
                `).join('');

                document.getElementById('devices').innerHTML = devicesHtml;
            } catch (error) {
                document.getElementById('devices').innerHTML = '<div class="error"><i class="fas fa-exclamation-circle"></i> Error loading devices</div>';
            }
        }
        
        async function discoverDevices() {
            const button = event.target;
            const originalHTML = button.innerHTML;
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Discovering...';

            try {
                const response = await fetch('/api/devices/discover', { method: 'POST' });
                const result = await response.json();

                if (result.success) {
                    showNotification(`Discovery complete! Found ${result.new_devices} new device(s).`, 'success');
                    await loadDevices();
                    await loadStatistics();
                } else {
                    showNotification(`Discovery failed: ${result.error}`, 'error');
                }
            } catch (error) {
                showNotification(`Discovery error: ${error.message}`, 'error');
            } finally {
                button.disabled = false;
                button.innerHTML = originalHTML;
            }
        }

        async function toggleLED(deviceIP) {
            try {
                // Use auto-mode setting (ESP-Linker v1.3.7+)
                const response = await fetch(`/api/devices/${deviceIP}/gpio`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: 'write',
                        pin: 2,
                        value: Math.random() > 0.5 ? 0 : 1,
                        auto_mode: true
                    })
                });

                if (response.ok) {
                    const result = await response.json();
                    showNotification(`LED toggled! Pin 2 = ${result.value}`, 'success');
                } else {
                    showNotification('Failed to toggle LED', 'error');
                }
            } catch (error) {
                showNotification(`Error: ${error.message}`, 'error');
            }
        }

        async function testPWM(deviceIP) {
            try {
                // Test PWM with 50% duty cycle
                const response = await fetch(`/api/devices/${deviceIP}/gpio`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: 'pwm',
                        pin: 4,
                        value: 512,
                        auto_mode: true
                    })
                });

                if (response.ok) {
                    showNotification('PWM test successful! Pin 4 = 50% duty cycle', 'success');
                } else {
                    showNotification('PWM test failed', 'error');
                }
            } catch (error) {
                showNotification(`Error: ${error.message}`, 'error');
            }
        }

        async function readAnalog(deviceIP) {
            try {
                const response = await fetch(`/api/devices/${deviceIP}/gpio`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: 'read',
                        pin: 'A0'
                    })
                });

                if (response.ok) {
                    const result = await response.json();
                    const voltage = (result.value * 3.3 / 1024).toFixed(2);
                    showNotification(`Analog reading: ${result.value} (${voltage}V)`, 'info');
                } else {
                    showNotification('Failed to read analog pin', 'error');
                }
            } catch (error) {
                showNotification(`Error: ${error.message}`, 'error');
            }
        }
        
        async function getStatus(deviceIP) {
            try {
                const response = await fetch(`/api/devices/${deviceIP}/status`);
                const status = await response.json();

                if (response.ok) {
                    const uptime = Math.round(status.uptime / 1000);
                    const uptimeStr = uptime > 3600 ? `${Math.round(uptime/3600)}h` : `${Math.round(uptime/60)}m`;
                    const memoryMB = (status.free_heap / 1024).toFixed(1);

                    showNotification(
                        `Device Status: Uptime ${uptimeStr}, Memory ${memoryMB}KB, WiFi: ${status.wifi_ssid}`,
                        'info'
                    );
                } else {
                    showNotification(`Status error: ${status.error}`, 'error');
                }
            } catch (error) {
                showNotification(`Error: ${error.message}`, 'error');
            }
        }

        function showNotification(message, type = 'info') {
            // Remove existing notifications
            const existing = document.querySelector('.notification');
            if (existing) existing.remove();

            // Create notification
            const notification = document.createElement('div');
            notification.className = `notification notification-${type}`;
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 16px 20px;
                border-radius: 8px;
                color: white;
                font-weight: 500;
                z-index: 1000;
                max-width: 400px;
                box-shadow: 0 4px 16px rgba(0,0,0,0.2);
                transform: translateX(100%);
                transition: transform 0.3s ease;
            `;

            // Set background color based on type
            const colors = {
                success: 'linear-gradient(135deg, #48bb78, #38a169)',
                error: 'linear-gradient(135deg, #f56565, #e53e3e)',
                info: 'linear-gradient(135deg, #4299e1, #3182ce)',
                warning: 'linear-gradient(135deg, #ed8936, #dd6b20)'
            };
            notification.style.background = colors[type] || colors.info;

            // Add icon
            const icons = {
                success: 'fas fa-check-circle',
                error: 'fas fa-exclamation-circle',
                info: 'fas fa-info-circle',
                warning: 'fas fa-exclamation-triangle'
            };

            notification.innerHTML = `
                <i class="${icons[type] || icons.info}"></i>
                <span style="margin-left: 8px;">${message}</span>
            `;

            document.body.appendChild(notification);

            // Animate in
            setTimeout(() => {
                notification.style.transform = 'translateX(0)';
            }, 100);

            // Auto-remove after 5 seconds
            setTimeout(() => {
                notification.style.transform = 'translateX(100%)';
                setTimeout(() => notification.remove(), 300);
            }, 5000);
        }

        // Advanced functions
        function refreshAll() {
            loadStatistics();
            loadDevices();
            showNotification('Dashboard refreshed', 'success');
        }

        function exportConfig() {
            const config = {
                devices: devices,
                timestamp: new Date().toISOString(),
                version: '1.3.6'
            };
            const blob = new Blob([JSON.stringify(config, null, 2)], {type: 'application/json'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'esp-linker-config.json';
            a.click();
            URL.revokeObjectURL(url);
            showNotification('Configuration exported', 'success');
        }

        function restartDevice(ip) {
            if (confirm(`Restart device at ${ip}?`)) {
                fetch(`/api/devices/${ip}/restart`, {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        showNotification(data.success ? 'Device restarting...' : 'Failed to restart device', data.success ? 'success' : 'error');
                        if (data.success) setTimeout(refreshAll, 3000);
                    })
                    .catch(error => showNotification('Error: ' + error.message, 'error'));
            }
        }

        function factoryReset(ip) {
            if (confirm(`Factory reset device at ${ip}? This will erase all settings!`)) {
                fetch(`/api/devices/${ip}/factory_reset`, {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        showNotification(data.success ? 'Device reset successfully' : 'Failed to reset device', data.success ? 'success' : 'error');
                        if (data.success) setTimeout(refreshAll, 3000);
                    })
                    .catch(error => showNotification('Error: ' + error.message, 'error'));
            }
        }

        // Load data on page load
        window.addEventListener('load', () => {
            loadStatistics();
            loadDevices();

            // Auto-refresh every 30 seconds
            setInterval(refreshAll, 30000);

            // Show welcome message
            setTimeout(() => {
                showNotification('ESP-Linker Dashboard loaded successfully!', 'success');
            }, 1000);
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

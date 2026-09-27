"""
py439 — Web dashboard with canvas-based real-time charts.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
import csv
import io
import json
import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

logger = logging.getLogger("py439")


class DashboardHandler(BaseHTTPRequestHandler):
    py439 = None

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_html()
        elif self.path == "/api/data":
            self._serve_api()
        elif self.path == "/api/export":
            self._serve_csv()
        else:
            self.send_error(404)

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

    def _serve_api(self):
        rtl = self.py439
        if rtl is None:
            self.send_error(500, "py439 not connected")
            return

        try:
            devices_data = []
            for key, rec in rtl.snapshot_devices():
                age = time.time() - rec.last_seen
                devices_data.append({
                    "protocol": rec.protocol,
                    "id": rec.id,
                    "channel": rec.channel,
                    "battery": rec.battery,
                    "temperature": rec.temperature,
                    "humidity": rec.humidity,
                    "pressure": rec.pressure,
                    "wind_speed": rec.wind_speed,
                    "wind_dir": rec.wind_dir,
                    "rain": rec.rain,
                    "uv": rec.uv,
                    "raw": rec.raw,
                    "crc_ok": rec.crc_ok,
                    "msg_count": rec.msg_count,
                    "age": round(age, 1),
                })

            uptime = time.time() - rtl.start_time
            response = {
                "status": "ok",
                "uptime": round(uptime, 1),
                "total_messages": rtl.total_messages,
                "crc_errors": rtl.crc_errors,
                "device_count": len(devices_data),
                "protocol_count": len(set(d["protocol"] for d in devices_data)),
                "msg_rate": round(rtl.total_messages / max(uptime, 1), 2),
                "devices": devices_data,
                "timestamp": time.time(),
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        except Exception as e:
            logger.error("API error: %s", e)
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))

    def _serve_csv(self):
        rtl = self.py439
        if rtl is None:
            self.send_error(500)
            return
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["protocol", "id", "channel", "battery", "temperature",
                         "humidity", "pressure", "wind_speed", "wind_dir",
                         "rain", "uv", "msg_count", "crc_ok"])
        for key, rec in rtl.snapshot_devices():
            writer.writerow([
                rec.protocol, rec.id, rec.channel, rec.battery,
                rec.temperature, rec.humidity, rec.pressure,
                rec.wind_speed, rec.wind_dir, rec.rain, rec.uv,
                rec.msg_count, rec.crc_ok,
            ])
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", "attachment; filename=py439_devices.csv")
        self.end_headers()
        self.wfile.write(buf.getvalue().encode("utf-8"))


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>py439 — SDR Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0f1117; color: #e0e0e0; font-family: 'Segoe UI', system-ui, sans-serif; }
.header { background: #1a1d29; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2a2d39; }
.header h1 { font-size: 20px; color: #fff; }
.header .status { display: flex; align-items: center; gap: 16px; }
.indicator { width: 12px; height: 12px; border-radius: 50%; background: #f00; transition: background 0.3s; }
.indicator.green { background: #0f0; }
.uptime { font-size: 13px; color: #888; }
.stats { display: flex; gap: 12px; padding: 16px 24px; flex-wrap: wrap; }
.stat-card { background: #1a1d29; border-radius: 10px; padding: 16px 24px; min-width: 140px; text-align: center; border: 1px solid #2a2d39; }
.stat-card .label { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.stat-card .value { font-size: 28px; font-weight: 700; }
.stat-card .value.green { color: #4caf50; }
.stat-card .value.orange { color: #ff9800; }
.stat-card .value.blue { color: #2196f3; }
.stat-card .value.red { color: #f44336; }
.charts { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 0 24px; }
.chart-box { background: #1a1d29; border-radius: 10px; padding: 16px; border: 1px solid #2a2d39; }
.chart-box h3 { font-size: 14px; color: #888; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; }
canvas { width: 100%; height: 200px; }
.devices { padding: 16px 24px; }
.devices h2 { font-size: 18px; margin-bottom: 12px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #2a2d39; font-size: 14px; }
th { color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
.badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge.green { background: #2e7d32; color: #c8e6c9; }
.badge.red { background: #c62828; color: #ffcdd2; }
.badge.orange { background: #ef6c00; color: #ffe0b2; }
.badge.gray { background: #455a64; color: #cfd8dc; }
.controls { display: flex; gap: 8px; padding: 0 24px 16px; }
.btn { background: #2a2d39; color: #e0e0e0; border: 1px solid #3a3d49; border-radius: 6px; padding: 8px 16px; cursor: pointer; font-size: 14px; }
.btn:hover { background: #3a3d49; }
</style>
</head>
<body>

<div class="header">
  <h1>📡 py439 Dashboard</h1>
  <div class="status">
    <span class="uptime" id="uptime">Uptime: --</span>
    <div class="indicator" id="indicator"></div>
  </div>
</div>

<div class="stats">
  <div class="stat-card"><div class="label">Devices</div><div class="value blue" id="stat-devices">0</div></div>
  <div class="stat-card"><div class="label">Messages</div><div class="value green" id="stat-messages">0</div></div>
  <div class="stat-card"><div class="label">Msg/s</div><div class="value orange" id="stat-rate">0</div></div>
  <div class="stat-card"><div class="label">Protocols</div><div class="value blue" id="stat-protocols">0</div></div>
  <div class="stat-card"><div class="label">CRC Errors</div><div class="value red" id="stat-crc">0</div></div>
</div>

<div class="controls">
  <button class="btn" id="btn-pause" onclick="togglePause()">⏸ Pause</button>
  <button class="btn" onclick="exportCSV()">📥 Export CSV</button>
</div>

<div class="charts">
  <div class="chart-box"><h3>Temperature (live)</h3><canvas id="chart-temp"></canvas></div>
  <div class="chart-box"><h3>Humidity (live)</h3><canvas id="chart-hum"></canvas></div>
  <div class="chart-box"><h3>Protocol Distribution</h3><canvas id="chart-pie"></canvas></div>
  <div class="chart-box"><h3>Message Rate</h3><canvas id="chart-bar"></canvas></div>
</div>

<div class="devices">
  <h2>Active Devices</h2>
  <table id="device-table">
    <thead>
      <tr><th>Protocol</th><th>ID</th><th>Ch</th><th>Temp</th><th>Hum</th><th>Battery</th><th>Msgs</th><th>CRC</th><th>Age</th></tr>
    </thead>
    <tbody id="device-body"></tbody>
  </table>
</div>

<script>
let paused = false;
let history = {}; // { deviceKey: { temp: [], hum: [], timestamps: [] } }
let msgRateHistory = [];
let protocolCounts = {};

const COLORS = ['#2196f3','#4caf50','#ff9800','#e91e63','#9c27b0','#00bcd4','#ffeb3b','#795548','#607d8b','#f44336','#009688','#673ab7'];

function api() {
  if (paused) return;
  fetch('/api/data').then(r => r.json()).then(data => {
    document.getElementById('indicator').className = 'indicator green';
    document.getElementById('uptime').textContent = 'Uptime: ' + Math.floor(data.uptime) + 's';
    document.getElementById('stat-devices').textContent = data.device_count;
    document.getElementById('stat-messages').textContent = data.total_messages;
    document.getElementById('stat-rate').textContent = data.msg_rate.toFixed(1);
    document.getElementById('stat-protocols').textContent = data.protocol_count;
    document.getElementById('stat-crc').textContent = data.crc_errors;

    // Update history
    data.devices.forEach((d, i) => {
      const key = d.protocol + ':' + d.id + ':ch' + d.channel;
      if (!history[key]) history[key] = { temp: [], hum: [], ts: [], color: COLORS[i % COLORS.length] };
      if (d.temperature !== null) {
        history[key].temp.push(d.temperature);
        history[key].ts.push(Date.now());
        if (history[key].temp.length > 60) { history[key].temp.shift(); history[key].ts.shift(); }
      }
      if (d.humidity !== null) {
        history[key].hum.push(d.humidity);
        if (history[key].hum.length > 60) history[key].hum.shift();
      }
    });

    // Protocol distribution
    protocolCounts = {};
    data.devices.forEach(d => { protocolCounts[d.protocol] = (protocolCounts[d.protocol] || 0) + 1; });

    // Message rate
    msgRateHistory.push(data.msg_rate);
    if (msgRateHistory.length > 60) msgRateHistory.shift();

    drawTempChart();
    drawHumChart();
    drawPieChart();
    drawBarChart();
    updateTable(data.devices);
  }).catch(() => {
    document.getElementById('indicator').className = 'indicator';
  });
}

function drawLineChart(ctx, datasets, yLabel, yMin, yMax) {
  const w = ctx.canvas.width = ctx.canvas.offsetWidth;
  const h = ctx.canvas.height = ctx.canvas.offsetHeight;
  ctx.clearRect(0, 0, w, h);

  // Grid
  ctx.strokeStyle = '#2a2d39';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = (h / 4) * i;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }

  // Y axis labels
  ctx.fillStyle = '#555';
  ctx.font = '10px sans-serif';
  for (let i = 0; i <= 4; i++) {
    const val = yMax - (yMax - yMin) * (i / 4);
    ctx.fillText(val.toFixed(0), 2, (h / 4) * i + 10);
  }

  // Lines
  Object.values(datasets).forEach(ds => {
    if (ds.temp.length < 1) return;
    ctx.strokeStyle = ds.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ds.temp.forEach((v, i) => {
      const x = (w / Math.max(ds.temp.length - 1, 1)) * i;
      const y = h - ((v - yMin) / (yMax - yMin)) * h;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
}

function drawTempChart() {
  const ctx = document.getElementById('chart-temp').getContext('2d');
  const w = ctx.canvas.width = ctx.canvas.offsetWidth;
  const h = ctx.canvas.height = ctx.canvas.offsetHeight;
  let allTemps = [];
  Object.values(history).forEach(ds => allTemps = allTemps.concat(ds.temp));
  let yMin = allTemps.length ? Math.min(...allTemps) - 2 : -10;
  let yMax = allTemps.length ? Math.max(...allTemps) + 2 : 40;
  drawLineChart(ctx, history, 'T', yMin, yMax);
  // Legend
  let legendY = h - 10;
  Object.entries(history).forEach(([key, ds], i) => {
    if (ds.temp.length < 1) return;
    ctx.fillStyle = ds.color;
    ctx.fillRect(w - 120, legendY - i * 14, 8, 8);
    ctx.fillStyle = '#888';
    ctx.font = '10px sans-serif';
    ctx.fillText(key.split(':')[0], w - 108, legendY - i * 14 + 8);
  });
}

function drawHumChart() {
  const ctx = document.getElementById('chart-hum').getContext('2d');
  const humData = {};
  Object.entries(history).forEach(([key, ds], i) => {
    if (ds.hum.length > 0) humData[key] = { temp: ds.hum, color: ds.color };
  });
  drawLineChart(ctx, humData, 'H', 0, 100);
}

function drawPieChart() {
  const ctx = document.getElementById('chart-pie').getContext('2d');
  const w = ctx.canvas.width = ctx.canvas.offsetWidth;
  const h = ctx.canvas.height = ctx.canvas.offsetHeight;
  ctx.clearRect(0, 0, w, h);

  const entries = Object.entries(protocolCounts);
  if (entries.length === 0) return;
  const total = entries.reduce((s, [_, v]) => s + v, 0);
  const cx = w / 2, cy = h / 2, r = Math.min(w, h) / 2 - 20;

  let angle = -Math.PI / 2;
  entries.forEach(([proto, count], i) => {
    const slice = (count / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, angle, angle + slice);
    ctx.closePath();
    ctx.fillStyle = COLORS[i % COLORS.length];
    ctx.fill();
    ctx.strokeStyle = '#0f1117';
    ctx.lineWidth = 2;
    ctx.stroke();

    const labelAngle = angle + slice / 2;
    const lx = cx + Math.cos(labelAngle) * (r * 0.6);
    const ly = cy + Math.sin(labelAngle) * (r * 0.6);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(Math.round(count / total * 100) + '%', lx, ly);
    angle += slice;
  });

  // Legend
  ctx.textAlign = 'left';
  entries.forEach(([proto, count], i) => {
    const ly = 10 + i * 14;
    ctx.fillStyle = COLORS[i % COLORS.length];
    ctx.fillRect(w - 110, ly, 8, 8);
    ctx.fillStyle = '#888';
    ctx.font = '10px sans-serif';
    ctx.fillText(proto + ' (' + count + ')', w - 98, ly + 8);
  });
}

function drawBarChart() {
  const ctx = document.getElementById('chart-bar').getContext('2d');
  const w = ctx.canvas.width = ctx.canvas.offsetWidth;
  const h = ctx.canvas.height = ctx.canvas.offsetHeight;
  ctx.clearRect(0, 0, w, h);

  if (msgRateHistory.length === 0) return;
  const maxVal = Math.max(...msgRateHistory, 1);
  const barW = w / msgRateHistory.length;

  msgRateHistory.forEach((v, i) => {
    const barH = (v / maxVal) * h;
    const hue = 120 - (v / maxVal) * 120;
    ctx.fillStyle = 'hsl(' + hue + ', 70%, 50%)';
    ctx.fillRect(i * barW, h - barH, barW - 1, barH);
  });

  ctx.fillStyle = '#555';
  ctx.font = '10px sans-serif';
  ctx.fillText('Max: ' + maxVal.toFixed(1) + ' msg/s', 4, 12);
}

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function updateTable(devices) {
  const tbody = document.getElementById('device-body');
  tbody.innerHTML = devices.map(d => {
    const ageColor = d.age < 10 ? 'green' : d.age < 60 ? 'orange' : 'red';
    const crcClass = d.crc_ok ? 'green' : 'red';
    const crcText = d.crc_ok ? 'OK' : 'FAIL';
    const batClass = d.battery === 'OK' ? 'green' : d.battery === 'LOW' ? 'red' : 'gray';
    return '<tr>'
      + '<td>' + escapeHtml(d.protocol) + '</td>'
      + '<td>' + escapeHtml(d.id) + '</td>'
      + '<td>' + d.channel + '</td>'
      + '<td>' + (d.temperature !== null ? d.temperature.toFixed(1) + '°C' : '-') + '</td>'
      + '<td>' + (d.humidity !== null ? d.humidity.toFixed(0) + '%' : '-') + '</td>'
      + '<td><span class="badge ' + batClass + '">' + (d.battery || '-') + '</span></td>'
      + '<td>' + d.msg_count + '</td>'
      + '<td><span class="badge ' + crcClass + '">' + crcText + '</span></td>'
      + '<td><span class="badge ' + ageColor + '">' + d.age.toFixed(0) + 's</span></td>'
      + '</tr>';
  }).join('');
}

function togglePause() {
  paused = !paused;
  document.getElementById('btn-pause').textContent = paused ? '▶ Resume' : '⏸ Pause';
}

function exportCSV() {
  window.location.href = '/api/export';
}

setInterval(api, 2000);
api();
</script>
</body>
</html>
"""


class DashboardServer:
    def __init__(self, port=8080, py439=None):
        self.port = port
        self.py439 = py439
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        DashboardHandler.py439 = self.py439
        self._server = HTTPServer(("127.0.0.1", self.port), DashboardHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None

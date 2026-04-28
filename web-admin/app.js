console.log('Leaflet disponible:', typeof L !== 'undefined');

const btnCheck = document.getElementById("btnCheck");
const output = document.getElementById("output");
const btnLatest = document.getElementById("btnLatest");
const btnHistory = document.getElementById("btnHistory");
const btnSendGps = document.getElementById("btnSendGps");
const btnMap = document.getElementById("btnMap");
const BASE = "http://127.0.0.1:5500";

// Variables globales para el mapa
window.map = null;
window.marker = null;

// Inicialización única al cargar el DOM
document.addEventListener('DOMContentLoaded', () => {
    const mapElement = document.getElementById('map');
    
    if (mapElement) {
        window.map = L.map('map').setView([40.7825, -73.9661], 15);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(window.map);
        window.marker = L.marker([40.7825, -73.9661]).addTo(window.map).bindPopup('Esperando GPS...');
        console.log('Mapa inicializado correctamente');
    } else {
        console.error('Error: div #map no encontrado');
    }
});

// Socket.io
const myToken = localStorage.getItem('access_token') || "";

if (!window.socket) {
    window.socket = io('http://127.0.0.1:5500', {
        transports: ['websocket'],
        query: {token: myToken},
        upgrade: false
    });
}
const socket = window.socket;

socket.on('connect', () => {
    console.log('Socket.io CONECTADO');
    output.textContent += '\nSocket.io listo (GPS cada 5s)';
});

socket.on('connect_error', (err) => {
    console.error('Error de conexión:', err.message);
});

socket.on('gps_live', (data) => {
    console.log('GPS RECIBIDO:', data);
    
    // Validar existencia de datos
    if (!data || data.lat === undefined) return;

    if (window.map) {
        if (window.marker) {
            window.marker.setLatLng([data.lat, data.lng]);
            window.marker.setPopupContent(`${data.bus_id || 'BUS'} | ${data.velocidad || 0} km/h`);
        } else {
            window.marker = L.marker([data.lat, data.lng]).addTo(window.map);
        }
        window.map.panTo([data.lat, data.lng]);
    }
});

// Event Listeners (Resto de botones)
btnCheck.addEventListener("click", async () => {
  try {
    const res = await fetch(`${BASE}/api/health`);
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
  } catch (err) { output.textContent = "Error: " + err; }
});

btnLatest.addEventListener("click", async () => {
  const res = await fetch(`${BASE}/api/buses/1/positions/latest`);
  const data = await res.json();
  output.textContent = JSON.stringify(data, null, 2);
});

btnHistory.addEventListener("click", async () => {
  const res = await fetch(`${BASE}/api/buses/1/positions`);
  const data = await res.json();
  output.textContent = JSON.stringify(data, null, 2);
});

btnSendGps.addEventListener("click", async () => {
  const res = await fetch(`${BASE}/api/gps/position`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_recorrido: 2, lat: 27.9675, lng: -110.9185 })
  });
  const data = await res.json();
  output.textContent = JSON.stringify(data, null, 2);
});

btnMap.addEventListener("click", async () => {
    if (!window.map) return;
    try {
        const res = await fetch(`${BASE}/api/buses/1/positions/latest`);
        const pos = await res.json();
        if (pos.lat && pos.lng) {
            window.marker.setLatLng([pos.lat, pos.lng]);
            window.map.setView([pos.lat, pos.lng], 16);
            output.textContent = `📍 Actualizado: ${pos.lat}, ${pos.lng}`;
        }
    } catch (e) { output.textContent = "Error mapa: " + e; }
});



document.getElementById("btnListBuses").addEventListener("click", async () => {
    const res = await fetch(`${BASE}/api/buses`);
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("btnGetBus").addEventListener("click", async () => {
    const id = prompt("ID de la unidad:");
    if (!id) return;
    const res = await fetch(`${BASE}/api/buses/${id}`);
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("btnCreateBus").addEventListener("click", async () => {
    const numero = prompt("Número económico (ej: POT-02):");
    const modelo = prompt("Modelo (ej: Vento 2023):");
    const placa  = prompt("Placa (ej: SON-002):");
    if (!numero || !placa) return;

    const res = await fetch(`${BASE}/api/buses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ numero_economico: numero, modelo, placa })
    });
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("btnUpdateBus").addEventListener("click", async () => {
    const id     = prompt("ID de la unidad a actualizar:");
    const numero = prompt("Nuevo número económico:");
    const modelo = prompt("Nuevo modelo:");
    const placa  = prompt("Nueva placa:");
    if (!id || !numero || !placa) return;

    const res = await fetch(`${BASE}/api/buses/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ numero_economico: numero, modelo, placa, activo: true })
    });
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("btnDeleteBus").addEventListener("click", async () => {
    const id = prompt("ID de la unidad a desactivar:");
    if (!id) return;
    const confirmar = confirm(`¿Desactivar unidad ${id}?`);
    if (!confirmar) return;

    const res = await fetch(`${BASE}/api/buses/${id}`, { method: "DELETE" });
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("btnEstadoBus").addEventListener("click", async () => {
    const id = prompt("ID de la unidad:");
    if (!id) return;
    const res = await fetch(`${BASE}/api/buses/${id}/estado`);
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

setInterval(async () => {
    try {
        // Consultamos la última posición real guardada en BD
        const res = await fetch(`${BASE}/api/buses/1/positions/latest`);
        const data = await res.json();
        
        if (data && data.lat && data.lng) {
            console.log('Última ubicación de BD:', data);
            
            // Actualizar marcador
            if (window.marker) {
                window.marker.setLatLng([data.lat, data.lng]);
            } else {
                window.marker = L.marker([data.lat, data.lng]).addTo(window.map);
            }
            // Mover el mapa a la nueva posición
            window.map.panTo([data.lat, data.lng]);
        }
    } catch (e) {
        console.warn("Esperando datos de la base de datos...");
    }
}, 5000); 

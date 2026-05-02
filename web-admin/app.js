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

socket.on('notificacion', (data) => {
    console.log('NOTIFICACION:', data);
    const color = data.tipo === 'retraso' ? '#ff4444' 
                : data.tipo === 'salida'  ? '#007bff' 
                : '#28a745';
    
    const div = document.createElement('div');
    div.style.cssText = `
        padding: 10px; margin: 5px 0; border-radius: 5px;
        background: ${color}; color: white; font-weight: bold;
    `;
    div.textContent = `${new Date().toLocaleTimeString('es-MX')} — ${data.mensaje}`;
    
    document.getElementById('notificaciones-panel').prepend(div);
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





document.getElementById("btnListRutas").addEventListener("click", async () => {
    const res = await fetch(`${BASE}/api/rutas`);
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("btnCreateRuta").addEventListener("click", async () => {
    const nombre  = prompt("Nombre de la ruta (ej: Ruta Empalme-Guaymas):");
    const origen  = prompt("Origen (ej: Empalme):");
    const destino = prompt("Destino (ej: ITSON Guaymas):");
    const desc    = prompt("Descripción (opcional):");
    if (!nombre || !origen || !destino) return;

    const res = await fetch(`${BASE}/api/rutas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre, descripcion: desc, origen, destino })
    });
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("btnGetParadas").addEventListener("click", async () => {
    const id = prompt("ID de la ruta:");
    if (!id) return;
    const res = await fetch(`${BASE}/api/rutas/${id}/paradas`);
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("btnAddParada").addEventListener("click", async () => {
    const id_ruta = prompt("ID de la ruta:");
    const nombre  = prompt("Nombre de la parada (ej: Campus ITSON):");
    const lat     = prompt("Latitud (ej: 27.9675):");
    const lng     = prompt("Longitud (ej: -110.9185):");
    const orden   = prompt("Orden en la ruta (ej: 1):");
    if (!id_ruta || !nombre) return;

    const res = await fetch(`${BASE}/api/rutas/${id_ruta}/paradas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre, latitud: lat, longitud: lng, orden: parseInt(orden) })
    });
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});



document.getElementById("btnMostrarRuta").addEventListener("click", async () => {
    // Limpiar marcadores de paradas anteriores
    if (window.paradaMarkers) {
        window.paradaMarkers.forEach(m => window.map.removeLayer(m));
    }
    if (window.rutaLine) {
        window.map.removeLayer(window.rutaLine);
    }
    window.paradaMarkers = [];

    const id = prompt("ID de la ruta:");
    if (!id) return;

    const res = await fetch(`${BASE}/api/rutas/${id}/paradas`);
    const paradas = await res.json();

    if (!paradas.length) {
        output.textContent = "No hay paradas en esta ruta.";
        return;
    }

    // Icono personalizado para paradas
    const iconoParada = L.divIcon({
        className: '',
        html: '🛑',
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    });

    const coordenadas = [];

    paradas.filter(p => p.latitud && p.longitud).forEach(parada => {
        const lat = parseFloat(parada.latitud);
        const lng = parseFloat(parada.longitud);
        coordenadas.push([lat, lng]);

        const marker = L.marker([lat, lng], { icon: iconoParada })
            .addTo(window.map)
            .bindPopup(`<b>Parada ${parada.orden}</b><br>${parada.nombre}`);

        window.paradaMarkers.push(marker);
    });

    // Línea conectando las paradas
    window.rutaLine = L.polyline(coordenadas, {
        color: '#007bff',
        weight: 4,
        dashArray: '10, 5'  // línea punteada
    }).addTo(window.map);

    // Centrar el mapa en la ruta
    window.map.fitBounds(window.rutaLine.getBounds(), { padding: [30, 30] });

    output.textContent = `Ruta mostrada con ${paradas.length} paradas`;
});



document.getElementById("btnListChoferes").addEventListener("click", async () => {
    const res = await fetch(`${BASE}/api/choferes`);
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("btnCreateChofer").addEventListener("click", async () => {
    const nombre   = prompt("Nombre:");
    const apellido = prompt("Apellido:");
    const telefono = prompt("Teléfono:");
    if (!nombre || !apellido) return;

    const res = await fetch(`${BASE}/api/choferes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre, apellido, telefono })
    });
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("btnUpdateChofer").addEventListener("click", async () => {
    const id       = prompt("ID del chofer a actualizar:");
    const nombre   = prompt("Nuevo nombre:");
    const apellido = prompt("Nuevo apellido:");
    const telefono = prompt("Nuevo teléfono:");
    if (!id || !nombre || !apellido) return;

    const res = await fetch(`${BASE}/api/choferes/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre, apellido, telefono, activo: true })
    });
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("btnDeleteChofer").addEventListener("click", async () => {
    const id = prompt("ID del chofer a desactivar:");
    if (!id) return;
    const confirmar = confirm(`¿Desactivar chofer ${id}?`);
    if (!confirmar) return;

    const res = await fetch(`${BASE}/api/choferes/${id}`, { method: "DELETE" });
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});




document.getElementById("btnEnviarNotificacion").addEventListener("click", async () => {
    const tipo    = prompt("Tipo (ej: salida, retraso, llegada):");
    const mensaje = prompt("Mensaje (ej: El bus salió de Empalme):");
    if (!tipo || !mensaje) return;

    const res = await fetch(`${BASE}/api/notificaciones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tipo, mensaje, id_recorrido: 1 })
    });
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
});




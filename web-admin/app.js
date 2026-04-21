console.log('Leaflet disponible:', typeof L !== 'undefined');

const btnCheck = document.getElementById("btnCheck");
const output = document.getElementById("output");
const btnLatest = document.getElementById("btnLatest");
const btnHistory = document.getElementById("btnHistory");
const btnSendGps = document.getElementById("btnSendGps");
const BASE = "http://127.0.0.1:5000";

let map = null;
let marker = null;

btnCheck.addEventListener("click", async () => {
  try {
    const res = await fetch("http://127.0.0.1:5000/api/health");
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    output.textContent = "Error conectando al backend: " + err;
  }
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
    body: JSON.stringify({ id_recorrido: 1, lat: 27.9675427, lng: -110.9185287 })
  });
  const data = await res.json();
  output.textContent = JSON.stringify(data, null, 2);
});

const btnMap = document.getElementById("btnMap");
btnMap.addEventListener("click", async () => {
    if (!map) {
        map = L.map('map').setView([27.9675427,-110.9185287], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(map);
        

        marker = L.marker([28.0094, -110.9108]).addTo(map)
            .bindPopup('Bus 1 - Esperando GPS...');
    }
    

    try {
        const res = await fetch(`${BASE}/api/buses/1/positions/latest`);
        const pos = await res.json();
        console.log("Posición mapa:", pos);  // DEBUG
        
        if (pos.lat && pos.lng) {
            if (marker) map.removeLayer(marker);
            

            marker = L.marker([pos.lat, pos.lng]).addTo(map)
                .bindPopup(`Bus 1<br>${new Date(pos.fecha_captura).toLocaleString('es-MX')}`);
            
            map.setView([parseFloat(pos.lat), parseFloat(pos.lng)], 16);
            output.textContent = `📍 Actualizado: ${parseFloat(pos.lat).toFixed(5)}, ${parseFloat(pos.lng).toFixed(5)}`;
        } else {
            output.textContent = "Sin posición GPS aún. Envía GPS primero.";
        }
    } catch (e) {
        console.error("Error mapa:", e);
        output.textContent = "Error mapa: " + e;
    }
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
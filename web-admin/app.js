const BASE = "http://10.232.36.55:5500";
const myToken = localStorage.getItem('access_token') || "";

// Variables globales para el mapa y capas
window.map = null;
window.marker = null;
window.paradaMarkers = [];
window.rutaLine = null;

/**
 * Funcionalidades para pantallas modales que servirán para CRUD
 * @param {"id del modal a abrir"} modalId 
 * @param {"información que ocupa los campos"} data 
 * @returns 
 */

function abrirModal(modalId, data = null) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.style.display = 'block';

    if (data) {
        if (modalId === 'modal-chofer') llenarCamposChofer(data);
        else if (modalId === 'modal-bus') llenarCamposBus(data);
        else if (modalId === 'modal-ruta') llenarCamposRuta(data);
    } else {
        const form = modal.querySelector('form');
        if (form) form.reset();
        resetearTitulos(modalId);
    }
}

/**
 * Funcionalidad para cerrar las pantallas modales
 * @param {"id del modal a cerrar"} modalId 
 */
function cerrarModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'none';
}

/**
 * Carga del mapa con ubicación inicial en CITEV
 */
document.addEventListener('DOMContentLoaded', () => {
    // 1. Inicializar Mapa
    const mapElement = document.getElementById('map');
    if (mapElement && typeof L !== 'undefined') {
        window.map = L.map('map').setView([27.9675, -110.9185], 14);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(window.map);
        
        window.marker = L.marker([27.9675, -110.9185]).addTo(window.map)
            .bindPopup('Esperando señal GPS...');
    }

    // 2. Personalización del Header
    const adminName = document.getElementById("admin-name");
    const nombreGuardado = localStorage.getItem("user_fullname"); 
    if (nombreGuardado && adminName) adminName.textContent = nombreGuardado;

    // 3. Carga inicial
    actualizarDashboardInicio();

    // 4. Navegación de Tabs
    const navItems = document.querySelectorAll('.nav-links li');
    const views = document.querySelectorAll('.content-view');

    /**
     * Esta es la navegación de la barra lateral
     */
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const viewName = item.innerText.trim().toLowerCase();
            if (viewName === 'choferes') cargarChoferes();
            if (viewName === 'camiones') cargarCamiones();
            if (viewName === 'rutas') cargarRutas();
            if (viewName === 'inicio') actualizarDashboardInicio();

            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            const targetId = `view-${viewName}`;
            views.forEach(view => view.style.display = (view.id === targetId) ? 'block' : 'none');
        });
    });

    // 5. Configurar Botones
    configurarBotonesAccion();
});

// --- LÓGICA DE DASHBOARD ---

/**
 * Esta función corresponde al Dashboard de las paradas y la información de rutas, 
 * se actualiza con la información real obtenida desde BD
 */
async function actualizarDashboardInicio() {
    try {
        // Paradas de la ruta 1
        const resStops = await fetch(`${BASE}/api/rutas/1/paradas`);
        if (resStops.ok) {
            const paradas = await resStops.json();
            const container = document.getElementById("stops-list");
            if (container && Array.isArray(paradas)) {
                container.innerHTML = paradas.length
                    ? paradas.map(p => `<div class="stop-item">📍 ${p.nombre}</div>`).join('')
                    : `<div class="stop-item">Sin paradas registradas</div>`;
            }
        }

        // Datos del bus 1
        const resBus = await fetch(`${BASE}/api/buses/1`);
        if (resBus.ok) {
            const bus = await resBus.json();
            if (document.getElementById("live-bus")) {
                document.getElementById("live-bus").textContent = bus.numero_economico || "---";
                document.getElementById("live-plate").textContent = bus.placa || "---";
            }
        }

        // Recorrido activo del bus 1
        const resRecorrido = await fetch(`${BASE}/api/buses/1/recorrido-activo`);
        if (resRecorrido.ok) {
            const recorrido = await resRecorrido.json();
            if (document.getElementById("live-shift")) {
                document.getElementById("live-shift").textContent = recorrido.hora_inicio
                    ? new Date(recorrido.hora_inicio).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
                    : "---";
            }
            if (document.getElementById("live-driver")) {
                document.getElementById("live-driver").textContent = recorrido.estado === 'activo' ? "En servicio" : "---";
            }
        }

        // Posición GPS más reciente → mover marcador en el mapa
        const resPos = await fetch(`${BASE}/api/buses/1/positions/latest`);
        if (resPos.ok) {
            const pos = await resPos.json();
            if (pos.lat && pos.lng && window.map && window.marker) {
                const newPos = [pos.lat, pos.lng];
                window.marker.setLatLng(newPos);
                window.map.panTo(newPos);
            }
        }

    } catch (err) { console.warn("Dashboard Error:", err); }
}

// --- CRUD TABLAS ---

/**
 * Función para gestión de los choferes, se obtiene, se puede editar, eliminar, etc.
 * @returns 
 */
async function cargarChoferes() {
    const tbody = document.getElementById("tbody-choferes");
    if (!tbody) return;
    try {
        const res = await fetch(`${BASE}/api/choferes`);
        const choferes = await res.json();
        tbody.innerHTML = choferes.map(chofer => `
            <tr>
                <td><img src="imagenes/chofericono.png" style="width: 35px;"></td>
                <td>${chofer.id.toString().padStart(3, '0')}</td>
                <td>${chofer.nombre} ${chofer.apellido}</td>
                <td>${chofer.genero || 'Hombre'}</td>
                <td>${chofer.telefono || 'N/A'}</td>
                <td>${chofer.unidad_asignada || '---'}</td>
                <td><span class="status-badge ${chofer.activo ? 'status-active' : 'status-inactive'}">${chofer.activo ? 'Activo' : 'Inactivo'}</span></td>
                <td class="actions">
                    <button onclick="prepararUpdateChofer(${chofer.id})" class="btn-edit">✎</button>
                    <button onclick="confirmarDeleteChofer(${chofer.id})" class="btn-delete">🗑</button>
                </td>
            </tr>
        `).join('');
    } catch (err) { console.error(err); }
}

/**
 * Función para gestión de los camiones, se obtiene, se puede editar, eliminar, etc
 * @returns 
 */
async function cargarCamiones() {
    const tbody = document.getElementById("tbody-camiones");
    if (!tbody) return;
    try {
        const res = await fetch(`${BASE}/api/buses`);
        const buses = await res.json();
        //se usa un emoji a falta de iconos😭
        tbody.innerHTML = buses.map(bus => `
            <tr>
                <td>🚌</td>
                <td>${bus.numero_economico || bus.id.toString().padStart(3, '0')}</td>
                <td>${bus.placa}</td>
                <td>${bus.modelo || 'N/A'}</td>
                <td>${bus.asignaciones || '---'}</td>
                <td><span class="status-badge ${bus.activo ? 'status-active' : 'status-inactive'}">${bus.activo ? 'Activo' : 'Inactivo'}</span></td>
                <td class="actions">
                    <button onclick="prepararUpdateBus(${bus.id})" class="btn-edit">✎</button>
                    <button onclick="confirmarDeleteBus(${bus.id})" class="btn-delete">🗑</button>
                </td>
            </tr>
        `).join('');
    } catch (err) { console.error(err); }
}

// --- MANEJADORES DE EVENTOS ---

/**
 * Función para el manejo de los diversos botones en el index.html
 */
function configurarBotonesAccion() {
    // BOTONES "AÑADIR" -> ABREN MODALES VACÍOS
    document.getElementById("btnCreateChofer")?.addEventListener("click", () => abrirModal('modal-chofer'));
    document.getElementById("btnCreateBus")?.addEventListener("click", () => abrirModal('modal-bus'));
    document.getElementById("btnCreateRuta")?.addEventListener("click", () => abrirModal('modal-ruta'));

    // SUBMITS DE FORMULARIOS
    document.getElementById("form-chofer")?.addEventListener("submit", manejarSubmitChofer);
    document.getElementById("form-bus")?.addEventListener("submit", manejarSubmitBus);
    document.getElementById("form-ruta")?.addEventListener("submit", manejarSubmitRuta);
    document.getElementById("form-parada")?.addEventListener("submit", manejarSubmitParada);

    // RUTA (PROMPT TEMPORAL)
    document.getElementById("btnMostrarRuta")?.addEventListener("click", () => {
        const id = prompt("ID de la ruta a visualizar:");
        if (id) mostrarRutaEnMapa(id);
    });

    window.onclick = (e) => {
        if (e.target.classList.contains('modal-overlay')) e.target.style.display = 'none';
    };
}

/**
 * La función para guardar la información del modal Chofer
 * @param {*} e 
 */
async function manejarSubmitChofer(e) {
    e.preventDefault();
    const id = document.getElementById('chofer-id').value;
    const payload = {
        nombre: document.getElementById('chofer-nombre').value,
        apellido: document.getElementById('chofer-apellido').value,
        genero: document.getElementById('chofer-genero').value,
        telefono: document.getElementById('chofer-telefono').value,
        activo: true
    };
    const res = await fetch(id ? `${BASE}/api/choferes/${id}` : `${BASE}/api/choferes`, {
        method: id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (res.ok) { cerrarModal('modal-chofer'); cargarChoferes(); }
}

/**
 * La función para guardar la información del modal Bus
 * @param {*} e 
 */
async function manejarSubmitBus(e) {
    e.preventDefault();
    const id = document.getElementById('bus-id').value;
    const payload = {
        numero_economico: document.getElementById('bus-numero').value,
        placa: document.getElementById('bus-placa').value,
        modelo: document.getElementById('bus-modelo').value,
        activo: true
    };
    const res = await fetch(id ? `${BASE}/api/buses/${id}` : `${BASE}/api/buses`, {
        method: id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (res.ok) { cerrarModal('modal-bus'); cargarCamiones(); }
}

// --- FUNCIONES DE APOYO ---

/**
 * Funciones para poblar las diversas tablas del index.html -> Chofer
 * @param {*} data 
 */
function llenarCamposChofer(data) {
    document.getElementById('modal-chofer-title').textContent = "Editar Chofer";
    document.getElementById('chofer-id').value = data.id;
    document.getElementById('chofer-nombre').value = data.nombre;
    document.getElementById('chofer-apellido').value = data.apellido;
    document.getElementById('chofer-genero').value = data.genero || 'Hombre';
    document.getElementById('chofer-telefono').value = data.telefono || "";
}

/**
 * Funciones para poblar las diversas tablas del index.html -> Autobus
 * @param {*} data 
 */
function llenarCamposBus(data) {
    document.getElementById('modal-bus-title').textContent = "Editar Unidad";
    document.getElementById('bus-id').value = data.id;
    document.getElementById('bus-numero').value = data.numero_economico;
    document.getElementById('bus-placa').value = data.placa;
    document.getElementById('bus-modelo').value = data.modelo || "";
}

function resetearTitulos(modalId) {
    if (modalId === 'modal-chofer') {
        document.getElementById('modal-chofer-title').textContent = "Nuevo Chofer";
        document.getElementById('chofer-id').value = "";
    } else if (modalId === 'modal-bus') {
        document.getElementById('modal-bus-title').textContent = "Nueva Unidad";
        document.getElementById('bus-id').value = "";
    } else if (modalId === 'modal-ruta') {
        document.getElementById('modal-ruta-title').textContent = "Nueva Ruta";
        document.getElementById('ruta-id').value = "";
    }
}

// FUNCIONES GLOBALES (LLAMADAS DESDE ONCLICK)
window.prepararUpdateChofer = async (id) => {
    const res = await fetch(`${BASE}/api/choferes/${id}`);
    const data = await res.json();
    abrirModal('modal-chofer', data);
};

window.prepararUpdateBus = async (id) => {
    const res = await fetch(`${BASE}/api/buses/${id}`);
    const data = await res.json();
    abrirModal('modal-bus', data);
};

window.confirmarDeleteChofer = async (id) => {
    if (confirm("¿Desactivar este chofer?")) {
        await fetch(`${BASE}/api/choferes/${id}`, { method: "DELETE" });
        cargarChoferes();
    }
};

window.confirmarDeleteBus = async (id) => {
    if (confirm("¿Desactivar este camión?")) {
        await fetch(`${BASE}/api/buses/${id}`, { method: "DELETE" });
        cargarCamiones();
    }
};

async function mostrarRutaEnMapa(id) {
    if (window.paradaMarkers.length > 0) {
        window.paradaMarkers.forEach(m => window.map.removeLayer(m));
        window.paradaMarkers = [];
    }
    if (window.rutaLine) window.map.removeLayer(window.rutaLine);

    try {
        const res = await fetch(`${BASE}/api/rutas/${id}/paradas`);
        const paradas = await res.json();
        if (!paradas.length) return alert("Ruta sin paradas");

        const coordenadas = [];
        paradas.forEach(p => {
            const pos = [parseFloat(p.latitud), parseFloat(p.longitud)];
            coordenadas.push(pos);
            const m = L.circleMarker(pos, { radius: 6, color: 'red' }).addTo(window.map).bindPopup(p.nombre);
            window.paradaMarkers.push(m);
        });

        window.rutaLine = L.polyline(coordenadas, { color: '#007bff', weight: 4 }).addTo(window.map);
        window.map.fitBounds(window.rutaLine.getBounds());
    } catch (e) { console.error(e); }
}

// SOCKETS
if (typeof io !== 'undefined') {
    window.socket = io(BASE, { transports: ['websocket'], query: { token: myToken } });
    window.socket.on('gps_live', (data) => {
        if (!data || data.lat === undefined) return;
        if (window.map && window.marker) {
            const newPos = [data.lat, data.lng];
            window.marker.setLatLng(newPos);
            window.map.panTo(newPos);
        }
    });
}
// --- RUTAS CRUD ---

async function cargarRutas() {
    const tbody = document.getElementById("tbody-rutas");
    if (!tbody) return;
    try {
        const res = await fetch(`${BASE}/api/rutas`);
        const rutas = await res.json();
        tbody.innerHTML = rutas.map(ruta => `
            <tr>
                <td>${ruta.id.toString().padStart(3, '0')}</td>
                <td>${ruta.nombre}</td>
                <td class="actions">
                    <button onclick="verParadas(${ruta.id}, '${ruta.nombre}')" class="btn-edit" title="Ver paradas">📍</button>
                    <button onclick="prepararUpdateRuta(${ruta.id})" class="btn-edit">✎</button>
                    <button onclick="confirmarDeleteRuta(${ruta.id})" class="btn-delete">🗑</button>
                </td>
            </tr>
        `).join('');
    } catch (err) { console.error(err); }
}

async function manejarSubmitRuta(e) {
    e.preventDefault();
    const id = document.getElementById('ruta-id').value;
    const payload = {
        nombre: document.getElementById('ruta-nombre').value
    };
    const res = await fetch(id ? `${BASE}/api/rutas/${id}` : `${BASE}/api/rutas`, {
        method: id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (res.ok) { cerrarModal('modal-ruta'); cargarRutas(); }
}

function llenarCamposRuta(data) {
    document.getElementById('modal-ruta-title').textContent = "Editar Ruta";
    document.getElementById('ruta-id').value = data.id;
    document.getElementById('ruta-nombre').value = data.nombre;
}

window.prepararUpdateRuta = async (id) => {
    const res = await fetch(`${BASE}/api/rutas/${id}`);
    const data = await res.json();
    abrirModal('modal-ruta', data);
};

window.confirmarDeleteRuta = async (id) => {
    if (confirm("¿Eliminar esta ruta?")) {
        await fetch(`${BASE}/api/rutas/${id}`, { method: "DELETE" });
        cargarRutas();
    }
};

// --- PARADAS ---

window.verParadas = async (idRuta, nombreRuta) => {
    document.getElementById('modal-paradas-title').textContent = `Paradas: ${nombreRuta}`;
    document.getElementById('parada-id-ruta').value = idRuta;
    document.getElementById('form-parada').reset();
    document.getElementById('modal-paradas').style.display = 'block';
    await cargarParadas(idRuta);
};

async function cargarParadas(idRuta) {
    const lista = document.getElementById('lista-paradas');
    lista.innerHTML = '<p style="color:#aaa">Cargando...</p>';
    try {
        const res = await fetch(`${BASE}/api/rutas/${idRuta}/paradas`);
        const paradas = await res.json();
        if (!paradas.length) {
            lista.innerHTML = '<p style="color:#aaa">Sin paradas registradas</p>';
            return;
        }
        lista.innerHTML = paradas.map(p => `
            <div class="parada-item">
                <span class="parada-orden">${p.orden}</span>
                <span class="parada-nombre">📍 ${p.nombre}</span>
            </div>
        `).join('');
    } catch (err) {
        lista.innerHTML = '<p style="color:#e74c3c">Error al cargar paradas</p>';
        console.error(err);
    }
}

async function manejarSubmitParada(e) {
    e.preventDefault();
    const idRuta = document.getElementById('parada-id-ruta').value;
    const payload = {
        nombre: document.getElementById('parada-nombre').value,
        latitud: parseFloat(document.getElementById('parada-latitud').value) || null,
        longitud: parseFloat(document.getElementById('parada-longitud').value) || null,
        orden: parseInt(document.getElementById('parada-orden').value) || 1
    };
    const res = await fetch(`${BASE}/api/rutas/${idRuta}/paradas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (res.ok) {
        document.getElementById('form-parada').reset();
        await cargarParadas(idRuta);
    }
}
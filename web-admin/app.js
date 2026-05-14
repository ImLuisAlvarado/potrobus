const BASE = "http://192.168.68.56:5500";

// Variables globales para el mapa y capas
window.map = null;
window.busMarkers = {};
window.paradaMarkers = [];
window.rutaLine = null;
window.recorridoLayers = {};

// --- INICIALIZACIÓN ---

document.addEventListener('DOMContentLoaded', () => {
    // Inicializar Mapa
    const mapElement = document.getElementById('map');
    if (mapElement && typeof L !== 'undefined') {
        window.map = L.map('map').setView([27.9675, -110.9185], 14);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(window.map);
    }

    // Nombre de Administrador
    const adminName = document.getElementById("admin-name");
    const nombreGuardado = localStorage.getItem("user_fullname");
    if (nombreGuardado && adminName) adminName.textContent = nombreGuardado;

    // Carga inicial
    actualizarDashboardInicio();

    // Navegación entre vistas
    const navItems = document.querySelectorAll('.nav-links li');
    const views = document.querySelectorAll('.content-view');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            // FIX #1: innerText captura también el alt/texto de íconos anidados.
            // Usamos el último nodo de texto del <li> para obtener solo el label.
            const rawText = Array.from(item.childNodes)
                .filter(n => n.nodeType === Node.TEXT_NODE)
                .map(n => n.textContent.trim())
                .join('').trim().toLowerCase();

            if (rawText === 'choferes') cargarChoferes();
            if (rawText === 'camiones') cargarCamiones();
            if (rawText === 'rutas') cargarRutas();
            if (rawText === 'inicio') actualizarDashboardInicio();

            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            const targetId = `view-${rawText}`;
            views.forEach(view => view.style.display = (view.id === targetId) ? 'block' : 'none');
        });
    });

    // FIX #2: conectar socket dentro de DOMContentLoaded, después de que el mapa existe
    if (typeof io !== 'undefined') {
        conectarSocketFlota();
    }

    configurarBotonesAccion();
});

// --- MODAL CERRAR SESIÓN ---
// FIX #3: función faltante referenciada en el HTML como onclick="confirmarCerrarSesion()"
// Su ausencia lanzaba ReferenceError al parsear el botón, rompiendo la ejecución del script.
function confirmarCerrarSesion() {
    const modal = document.getElementById('modal-logout');
    if (modal) modal.style.display = 'block';
}

// --- LÓGICA DE DASHBOARD (FLOTA EN TIEMPO REAL) ---

// Caché de buses activos para consulta rápida desde el socket
window.busesActivosCache = {};

async function actualizarDashboardInicio() {
    if (!window.map) return;

    try {
        const resBuses = await fetch(`${BASE}/api/buses/activos`);
        if (!resBuses.ok) return;

        const busesActivos = await resBuses.json();

        // Actualizar caché global
        window.busesActivosCache = {};
        busesActivos.forEach(b => { window.busesActivosCache[b.id_unidad] = b; });

        // Limpiar del mapa buses que ya no están activos
        const idsActivos = busesActivos.map(b => b.id_unidad.toString());
        Object.keys(window.busMarkers).forEach(id => {
            if (!idsActivos.includes(id.toString())) {
                window.map.removeLayer(window.busMarkers[id]);
                delete window.busMarkers[id];
            }
        });

        // Cargar/Actualizar posición de cada bus activo
        let busesEnRuta = 0;
        for (const bus of busesActivos) {
            const colocado = await cargarPosicionBusEnMapa(bus);
            if (colocado) busesEnRuta++;
        }

        // Actualizar cards de resumen de flota
        actualizarResumenFlota(busesActivos.length, busesEnRuta);

    } catch (err) {
        console.warn("Error en Dashboard:", err);
    }
}

// Actualiza las 4 cards con el resumen general de la flota
function actualizarResumenFlota(totalActivos, enRuta) {
    const sinSenal = totalActivos - enRuta;
    document.getElementById('live-driver').textContent = `${enRuta} en ruta`;
    document.getElementById('live-shift').textContent = new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
    document.getElementById('live-bus').textContent = `${totalActivos} unidad${totalActivos !== 1 ? 'es' : ''}`;
    document.getElementById('live-plate').textContent = sinSenal > 0 ? `${sinSenal} sin señal` : 'Todas OK';
}

// Muestra el detalle de un bus específico al hacer clic en su marcador
function mostrarDetallesBus(bus, pos) {
    document.getElementById('label-driver').textContent = 'Unidad';
    document.getElementById('label-shift').textContent  = 'Últ. señal';
    document.getElementById('label-bus').textContent    = 'Modelo';
    document.getElementById('label-plate').textContent  = 'Placa';

    document.getElementById('live-driver').textContent = bus.numero_economico;
    document.getElementById('live-shift').textContent  = pos.timestamp || 'Reciente';
    document.getElementById('live-bus').textContent    = bus.modelo || 'N/A';
    document.getElementById('live-plate').textContent  = bus.placa;
}

// Restablece las cards al resumen general
function restablecerResumen() {
    document.getElementById('label-driver').textContent = 'En ruta';
    document.getElementById('label-shift').textContent  = 'Hora';
    document.getElementById('label-bus').textContent    = 'Unidades activas';
    document.getElementById('label-plate').textContent  = 'Estado señal';

    const total = Object.keys(window.busesActivosCache).length;
    const enRuta = Object.keys(window.busMarkers).length;
    actualizarResumenFlota(total, enRuta);
}

// Devuelve true si logró colocar el marcador en el mapa
async function cargarPosicionBusEnMapa(bus) {
    try {
        const resPos = await fetch(`${BASE}/api/buses/${bus.id_unidad}/positions/latest`);

        if (!resPos.ok) {
            console.log(`Unidad ${bus.id_unidad} sin posición previa. Esperando señal GPS...`);
            return false;
        }

        const pos = await resPos.json();
        if (pos.error === "sin_posicion" || !pos.lat) return false;

        const id = bus.id_unidad;
        const popup = `
            <strong>Unidad: ${bus.numero_economico}</strong><br>
            Placa: ${bus.placa}<br>
            <small>Última actualización: ${pos.timestamp || 'Reciente'}</small>
        `;

        if (!window.busMarkers[id]) {
            window.busMarkers[id] = L.marker([pos.lat, pos.lng])
                .addTo(window.map)
                .bindPopup(popup)
                .on('click', () => mostrarDetallesBus(bus, pos))    // clic → detalle
                .on('popupclose', () => restablecerResumen());       // cierre → resumen
        } else {
            window.busMarkers[id].setLatLng([pos.lat, pos.lng]);
            window.busMarkers[id].setPopupContent(popup);
        }
        return true;
    } catch (err) {
        console.error(`Error posición bus ${bus.id_unidad}:`, err);
        return false;
    }
}

// --- CONFIGURACIÓN DE SOCKETS ---

function conectarSocketFlota() {
    // FIX #2 (continuación): leer el token en el momento de conectar, no al cargar el script
    const token = localStorage.getItem('access_token');
    if (!token || typeof io === 'undefined') {
        console.warn("Socket no conectado: token ausente o socket.io no disponible.");
        return;
    }

    window.socket = io(BASE, {
        transports: ['websocket'],
        query: { token }
    });

    // FIX #5: agregar handlers de conexión para diagnóstico y reconexión
    window.socket.on('connect', () => {
        console.log("✅ Socket conectado:", window.socket.id);
    });

    window.socket.on('connect_error', (err) => {
        console.error("❌ Error de conexión socket:", err.message);
    });

    window.socket.on('disconnect', (reason) => {
        console.warn("⚠️ Socket desconectado:", reason);
    });

    window.socket.on('gps_live', (data) => {
        console.log("GPS recibido:", data);
        if (!data || data.lat == null || data.lng == null) return;

        const idBus = data.id_unidad;
        if (!idBus || !window.map) return;

        const newPos = [data.lat, data.lng];
        const bus = window.busesActivosCache[idBus];

        if (!window.busMarkers[idBus]) {
            window.busMarkers[idBus] = L.marker(newPos)
                .addTo(window.map)
                .bindPopup(`<strong>Unidad: ${data.bus_id || idBus}</strong>`)
                .on('click', () => {
                    if (bus) mostrarDetallesBus(bus, data);
                })
                .on('popupclose', () => restablecerResumen());
        } else {
            window.busMarkers[idBus].setLatLng(newPos);
        }

        // Si el popup de este bus está abierto, actualizar las cards en tiempo real
        if (window.busMarkers[idBus].isPopupOpen() && bus) {
            mostrarDetallesBus(bus, data);
        }
    });
}

// --- CRUD: CHOFERES ---

async function cargarChoferes() {
    const tbody = document.getElementById("tbody-choferes");
    if (!tbody) return;
    try {
        const res = await fetch(`${BASE}/api/choferes`);
        const choferes = await res.json();
        tbody.innerHTML = choferes.map(chofer => {
            const estaActivo = chofer.activo;
            return `
            <tr>
                <td><img src="imagenes/chofericono.png" style="width: 35px;"></td>
                <td>${chofer.id_chofer.toString().padStart(3, '0')}</td>
                <td>${chofer.nombre} ${chofer.apellido}</td>
                <td>${chofer.genero || 'Hombre'}</td>
                <td>${chofer.telefono || 'N/A'}</td>
                <td>${chofer.numero_economico || '---'}</td>
                <td><span class="status-badge ${estaActivo ? 'status-active' : 'status-inactive'}">${estaActivo ? 'Activo' : 'Inactivo'}</span></td>
                <td class="actions">
                    <button onclick="window.prepararUpdateChofer(${chofer.id_chofer})" class="btn-edit">✎</button>
                    <button onclick="window.toggleEstadoChofer(${chofer.id_chofer}, ${estaActivo})"
                            class="${estaActivo ? 'btn-desactivar' : 'btn-activar'}">
                        ${estaActivo ? '🚫' : '✅'}
                    </button>
                </td>
            </tr>`;
        }).join('');
    } catch (err) { console.error(err); }
}

// --- CRUD: CAMIONES ---

async function cargarCamiones() {
    const tbody = document.getElementById("tbody-camiones");
    if (!tbody) return;
    try {
        const res = await fetch(`${BASE}/api/buses`);
        const buses = await res.json();
        tbody.innerHTML = buses.map(bus => {
            const unidadActiva = bus.activo;
            return `
            <tr>
                <td>🚌</td>
                <td>${bus.numero_economico}</td>
                <td>${bus.placa}</td>
                <td>${bus.modelo || 'N/A'}</td>
                <td><span class="status-badge ${unidadActiva ? 'status-active' : 'status-inactive'}">${unidadActiva ? 'Activo' : 'Inactivo'}</span></td>
                <td class="actions">
                    <button onclick="window.prepararUpdateBus(${bus.id_unidad})" class="btn-edit">✎</button>
                    <button onclick="window.toggleEstadoUnidad(${bus.id_unidad}, ${unidadActiva})"
                            class="${unidadActiva ? 'btn-desactivar' : 'btn-activar'}">
                        ${unidadActiva ? '🚫' : '✅'}
                    </button>
                </td>
            </tr>`;
        }).join('');
    } catch (err) { console.error(err); }
}

// --- CRUD: RUTAS ---

async function cargarRutas() {
    const tbody = document.getElementById("tbody-rutas");
    if (!tbody) return;
    try {
        const res = await fetch(`${BASE}/api/rutas`);
        const rutas = await res.json();
        tbody.innerHTML = rutas.map(ruta => `
            <tr>
                <td>${ruta.id_ruta.toString().padStart(3, '0')}</td>
                <td>${ruta.nombre}</td>
                <td class="actions">
                    <button onclick="verParadas(${ruta.id_ruta}, '${ruta.nombre}')" class="btn-edit" title="Ver paradas">📍</button>
                    <button onclick="prepararUpdateRuta(${ruta.id_ruta})" class="btn-edit">✎</button>
                    <button onclick="confirmarDeleteRuta(${ruta.id_ruta})" class="btn-delete">🗑</button>
                </td>
            </tr>
        `).join('');
    } catch (err) { console.error(err); }
}

// --- MANEJADORES DE SUBMIT Y MODALES ---

function configurarBotonesAccion() {
    document.getElementById("btnCreateChofer")?.addEventListener("click", () => abrirModal('modal-chofer', null));
    document.getElementById("btnCreateBus")?.addEventListener("click", () => abrirModal('modal-bus'));
    document.getElementById("btnCreateRuta")?.addEventListener("click", () => abrirModal('modal-ruta'));

    document.getElementById("form-chofer")?.addEventListener("submit", manejarSubmitChofer);
    document.getElementById("form-bus")?.addEventListener("submit", manejarSubmitBus);
    document.getElementById("form-ruta")?.addEventListener("submit", manejarSubmitRuta);
    document.getElementById("form-parada")?.addEventListener("submit", manejarSubmitParada);

    document.getElementById("btnMostrarRuta")?.addEventListener("click", () => {
        const id = prompt("ID de la ruta a visualizar:");
        if (id) mostrarRutaEnMapa(id);
    });

    window.onclick = (e) => {
        if (e.target.classList.contains('modal-overlay')) e.target.style.display = 'none';
    };
}

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
    if (res.ok) { cerrarModal('modal-bus'); cargarCamiones(); actualizarDashboardInicio(); }
}

async function manejarSubmitChofer(e) {
    e.preventDefault();
    const id          = document.getElementById('chofer-id').value;
    const idUnidadRaw = document.getElementById('chofer-unidad-select').value;
    const password    = document.getElementById('chofer-password').value;
    const payload = {
        nombre:    document.getElementById('chofer-nombre').value,
        apellido:  document.getElementById('chofer-apellido').value,
        genero:    document.getElementById('chofer-genero').value,
        telefono:  document.getElementById('chofer-telefono').value,
        correo:    document.getElementById('chofer-correo').value || null,
        id_unidad: idUnidadRaw ? parseInt(idUnidadRaw) : null,
        activo:    true
    };
    // Solo incluir password si el admin escribió uno (al crear es obligatorio, al editar es opcional)
    if (password) payload.password = password;
    const res = await fetch(id ? `${BASE}/api/choferes/${id}` : `${BASE}/api/choferes`, {
        method: id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (res.ok) { cerrarModal('modal-chofer'); cargarChoferes(); }
}

// --- FUNCIONES DE APOYO (MODALES) ---

function abrirModal(modalId, data = null) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.style.display = 'block';

    if (data) {
        if (modalId === 'modal-chofer') {
            poblarSelectUnidades(data.id_unidad ?? null).then(() => llenarCamposChofer(data));
        }
        else if (modalId === 'modal-bus') llenarCamposBus(data);
        else if (modalId === 'modal-ruta') llenarCamposRuta(data);
    } else {
        const form = modal.querySelector('form');
        if (form) form.reset();
        resetearTitulos(modalId);
        if (modalId === 'modal-chofer') poblarSelectUnidades(null);
    }
}

function cerrarModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'none';
}

function llenarCamposBus(data) {
    document.getElementById('modal-bus-title').textContent = "Editar Unidad";
    document.getElementById('bus-id').value = data.id_unidad;
    document.getElementById('bus-numero').value = data.numero_economico;
    document.getElementById('bus-placa').value = data.placa;
    document.getElementById('bus-modelo').value = data.modelo || "";
}

// Puebla el select de unidades con los buses activos.
// selectedId: id_unidad a preseleccionar (null = "Sin asignar")
async function poblarSelectUnidades(selectedId = null) {
    const select = document.getElementById('chofer-unidad-select');
    if (!select) return;

    select.innerHTML = '<option value="">Cargando unidades...</option>';
    select.disabled = true;

    try {
        const res = await fetch(`${BASE}/api/buses/activos`);
        const buses = await res.json();

        select.innerHTML = '<option value="">Sin asignar</option>';
        buses.forEach(bus => {
            const opt = document.createElement('option');
            opt.value = bus.id_unidad;
            opt.textContent = `${bus.numero_economico} — ${bus.placa}`;
            if (selectedId && bus.id_unidad == selectedId) opt.selected = true;
            select.appendChild(opt);
        });
    } catch {
        select.innerHTML = '<option value="">Error al cargar unidades</option>';
    } finally {
        select.disabled = false;
    }
}

function llenarCamposChofer(data) {
    document.getElementById('modal-chofer-title').textContent      = "Editar Chofer";
    document.getElementById('chofer-id').value                     = data.id_chofer;
    document.getElementById('chofer-nombre').value                 = data.nombre;
    document.getElementById('chofer-apellido').value               = data.apellido;
    document.getElementById('chofer-genero').value                 = data.genero || 'Hombre';
    document.getElementById('chofer-telefono').value               = data.telefono || "";
    document.getElementById('chofer-correo').value                 = data.correo || "";
    document.getElementById('chofer-password').value               = ""; // nunca mostrar hash
    document.getElementById('hint-chofer-password').style.display  = 'block';
    document.getElementById('label-chofer-password').textContent   = "Nueva contraseña:";
    // La unidad ya fue preseleccionada por poblarSelectUnidades antes de llamar esta función
}

function resetearTitulos(modalId) {
    if (modalId === 'modal-chofer') {
        document.getElementById('modal-chofer-title').textContent      = "Nuevo Chofer";
        document.getElementById('chofer-id').value                     = "";
        document.getElementById('hint-chofer-password').style.display  = 'none';
        document.getElementById('label-chofer-password').textContent   = "Contraseña:";
    } else if (modalId === 'modal-bus') {
        document.getElementById('modal-bus-title').textContent = "Nueva Unidad";
        document.getElementById('bus-id').value = "";
    } else if (modalId === 'modal-ruta') {
        document.getElementById('modal-ruta-title').textContent = "Nueva Ruta";
        document.getElementById('ruta-id').value = "";
    }
}

// --- EXPOSICIÓN DE FUNCIONES A WINDOW PARA BOTONES HTML ---

window.prepararUpdateBus = async (id) => {
    const res = await fetch(`${BASE}/api/buses/${id}`);
    const data = await res.json();
    abrirModal('modal-bus', data);
};

window.prepararUpdateChofer = async (id) => {
    const res = await fetch(`${BASE}/api/choferes/${id}`);
    const data = await res.json();
    // abrirModal detecta modal-chofer y llama poblarSelectUnidades(data.id_unidad) antes de llenar campos
    abrirModal('modal-chofer', data);
};

window.toggleEstadoUnidad = async (id, estadoActual) => {
    const nuevoEstado = !estadoActual;
    if (confirm(nuevoEstado ? "¿Reactivar unidad?" : "¿Desactivar unidad?")) {
        await fetch(`${BASE}/api/buses/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ activo: nuevoEstado })
        });
        cargarCamiones();
        actualizarDashboardInicio();
    }
};

window.toggleEstadoChofer = async (id, estadoActual) => {
    const nuevoEstado = !estadoActual;
    if (confirm(nuevoEstado ? "¿Reactivar chofer?" : "¿Desactivar chofer?")) {
        await fetch(`${BASE}/api/choferes/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ activo: nuevoEstado })
        });
        cargarChoferes();
    }
};

// --- PARADAS Y RUTAS (VISUALIZACIÓN) ---

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
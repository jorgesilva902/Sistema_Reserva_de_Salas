/**
 * ============================================================================
 * SISTEMA DE RESERVA DE SALAS ACADÉMICAS
 * Lógica Frontend SPA (Single Page Application) en Vanilla JavaScript (ES6+)
 * ============================================================================
 * 
 * Aspectos Clave de Arquitectura:
 * 1. Manejo de Sesión y Token JWT con LocalStorage.
 * 2. Cliente HTTP Centralizado (apiFetch) con Interceptor de Errores Globales (401).
 * 3. Enrutamiento SPA dinámico mediante manipulación del DOM.
 * 4. Control de Concurrencia Transaccional en tiempo real (Manejo de HTTP 409 Conflict).
 */

// ----------------------------------------------------------------------------
// 1. CONFIGURACIÓN Y CONSTANTES DEL CLIENTE
// ----------------------------------------------------------------------------
// Si el frontend se sirve desde el mismo servidor FastAPI usa la ruta relativa,
// si se abre con Live Server o file:// usa el origen absoluto.
const API_BASE = window.location.origin.includes('8000')
  ? `${window.location.origin}/api`
  : 'http://127.0.0.1:8000/api';

const STORAGE_KEYS = {
  TOKEN: 'app_jwt_token',
  USER: 'app_user_profile',
};

// Estado local de la aplicación (In-Memory State)
const state = {
  token: localStorage.getItem(STORAGE_KEYS.TOKEN) || null,
  user: JSON.parse(localStorage.getItem(STORAGE_KEYS.USER) || 'null'),
  salas: [],
  reservas: [],
  salaSeleccionada: null,
};

// ----------------------------------------------------------------------------
// 2. INTERCEPTOR HTTP GLOBAL Y GESTIÓN DE TOKEN (LocalStorage)
// ----------------------------------------------------------------------------
/**
 * Realiza peticiones HTTP a la API REST centralizando:
 * - Inyección automática del Header 'Authorization: Bearer <token>'.
 * - Intercepción de respuestas HTTP 401 (Token vencido o inválido).
 *   En caso de 401, destruye la sesión y redirige al formulario de Login.
 * 
 * @param {string} endpoint - Ruta relativa del recurso (ej: '/salas/')
 * @param {object} options  - Opciones estándar de la Fetch API (method, body, etc.)
 * @returns {Promise<Response>}
 */
async function apiFetch(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  // Inyección del token Bearer si existe en el estado o LocalStorage
  if (state.token) {
    headers.set('Authorization', `Bearer ${state.token}`);
  }

  // Si se envía JSON en el body y no se especificó Content-Type, agregarlo
  if (options.body && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const config = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);

    // INTERCEPTOR GLOBAL: Si la API responde 401 Unauthorized
    // significa que el JWT expiró, fue revocado o es inválido.
    if (response.status === 401) {
      console.warn('[Security] Token expirado o no autorizado (401). Forzando cierre de sesión...');
      cerrarSesion(true); // Cierra sesión y alerta al usuario
      throw new Error('Sesión expirada. Por favor ingresa nuevamente.');
    }

    return response;
  } catch (error) {
    // Si la conexión falla por corte de red o servidor caído
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      console.error('[Network Error] No se pudo conectar con el backend en:', url);
      showToast('No hay conexión con el servidor. Revisa que FastAPI esté activo.', 'error');
    }
    throw error;
  }
}

// ----------------------------------------------------------------------------
// 3. CONTROLADOR DE VISTAS Y NAVEGACIÓN (SPA)
// ----------------------------------------------------------------------------
const DOM = {
  // Vistas principales
  viewLogin: document.getElementById('view-login'),
  viewDashboard: document.getElementById('view-dashboard'),

  // Formularios
  formLogin: document.getElementById('form-login'),
  loginEmail: document.getElementById('login-email'),
  loginPassword: document.getElementById('login-password'),
  btnLoginSubmit: document.getElementById('btn-login-submit'),
  loginAlert: document.getElementById('login-alert'),
  loginAlertMsg: document.getElementById('login-alert-msg'),

  // Navbar
  navUserName: document.getElementById('nav-user-name'),
  navUserRole: document.getElementById('nav-user-role'),
  btnLogout: document.getElementById('btn-logout'),
  tabSalas: document.getElementById('tab-salas'),
  tabReservas: document.getElementById('tab-reservas'),
  tabAdmin: document.getElementById('tab-admin'),
  badgeReservasCount: document.getElementById('badge-reservas-count'),

  // Paneles de contenido
  panelSalas: document.getElementById('panel-salas'),
  panelReservas: document.getElementById('panel-reservas'),
  panelAdmin: document.getElementById('panel-admin'),

  // Admin
  btnNuevaSala: document.getElementById('btn-nueva-sala'),
  btnRefreshAdmin: document.getElementById('btn-refresh-admin'),
  adminSalasTbody: document.getElementById('admin-salas-tbody'),
  adminSalasEmpty: document.getElementById('admin-salas-empty'),
  adminTiposTbody: document.getElementById('admin-tipos-tbody'),
  formNuevoTipo: document.getElementById('form-nuevo-tipo'),
  tipoAcronimo: document.getElementById('tipo-acronimo'),
  tipoDescripcion: document.getElementById('tipo-descripcion'),
  modalSala: document.getElementById('modal-sala'),
  modalSalaTitulo: document.getElementById('modal-sala-titulo'),
  formSala: document.getElementById('form-sala'),
  salaIdEdit: document.getElementById('sala-id-edit'),
  salaAcronimo: document.getElementById('sala-acronimo'),
  salaNumero: document.getElementById('sala-numero'),
  salaCapacidad: document.getElementById('sala-capacidad'),
  salaHabilitada: document.getElementById('sala-habilitada'),
  btnCloseModalSala: document.getElementById('btn-close-modal-sala'),
  btnCancelarModalSala: document.getElementById('btn-cancelar-modal-sala'),
  salasGrid: document.getElementById('salas-grid'),
  salasLoading: document.getElementById('salas-loading'),
  salasEmpty: document.getElementById('salas-empty'),
  inputFiltroSala: document.getElementById('input-filtro-sala'),
  btnRefreshSalas: document.getElementById('btn-refresh-salas'),

  // Reservas
  reservasList: document.getElementById('reservas-list'),
  reservasLoading: document.getElementById('reservas-loading'),
  reservasEmpty: document.getElementById('reservas-empty'),
  btnRefreshReservas: document.getElementById('btn-refresh-reservas'),
  btnIrASalas: document.getElementById('btn-ir-a-salas'),

  // Modal de Reserva
  modalReserva: document.getElementById('modal-reserva'),
  modalSalaNombre: document.getElementById('modal-sala-nombre'),
  modalSalaCapacidad: document.getElementById('modal-sala-capacidad'),
  modalAlertConflict: document.getElementById('modal-alert-conflict'),
  modalAlertText: document.getElementById('modal-alert-text'),
  modalAlertSuccess: document.getElementById('modal-alert-success'),
  formCrearReserva: document.getElementById('form-crear-reserva'),
  reservaSalaId: document.getElementById('reserva-sala-id'),
  reservaFecha: document.getElementById('reserva-fecha'),
  reservaHora: document.getElementById('reserva-hora'),
  reservaDuracion: document.getElementById('reserva-duracion'),
  btnCloseModal: document.getElementById('btn-close-modal'),
  btnCancelarModal: document.getElementById('btn-cancelar-modal'),
  btnSubmitReserva: document.getElementById('btn-submit-reserva'),

  // Toasts
  toastContainer: document.getElementById('toast-container'),
};

/**
 * Cambia dinámicamente entre la vista de Login y la del Dashboard
 */
function cambiarVista(vistaDestino) {
  if (vistaDestino === 'dashboard') {
    DOM.viewLogin.classList.remove('active');
    DOM.viewLogin.classList.add('hidden');
    DOM.viewDashboard.classList.remove('hidden');
    DOM.viewDashboard.classList.add('active');
  } else {
    DOM.viewDashboard.classList.remove('active');
    DOM.viewDashboard.classList.add('hidden');
    DOM.viewLogin.classList.remove('hidden');
    DOM.viewLogin.classList.add('active');
  }
}

/**
 * Conmuta entre las pestañas "Salas Disponibles" y "Mis Reservas"
 */
function cambiarPestana(targetPanelId) {
  const isSalas = targetPanelId === 'panel-salas';
  const isReservas = targetPanelId === 'panel-reservas';
  const isAdmin = targetPanelId === 'panel-admin';

  DOM.tabSalas.classList.toggle('active', isSalas);
  DOM.tabReservas.classList.toggle('active', isReservas);
  DOM.tabAdmin.classList.toggle('active', isAdmin);

  DOM.panelSalas.classList.toggle('hidden', !isSalas);
  DOM.panelSalas.classList.toggle('active', isSalas);

  DOM.panelReservas.classList.toggle('hidden', !isReservas);
  DOM.panelReservas.classList.toggle('active', isReservas);

  DOM.panelAdmin.classList.toggle('hidden', !isAdmin);
  DOM.panelAdmin.classList.toggle('active', isAdmin);

  if (isReservas) {
    cargarReservas();
  }
  if (isAdmin) {
    cargarAdminSalas();
    cargarTiposSala();
  }
}

// ----------------------------------------------------------------------------
// 4. AUTENTICACIÓN (LOGIN Y LOGOUT)
// ----------------------------------------------------------------------------
/**
 * Inicia sesión mediante POST /api/auth/login usando x-www-form-urlencoded
 */
async function iniciarSesion(event) {
  event.preventDefault();
  ocultarAlertaLogin();

  const email = DOM.loginEmail.value.trim();
  const password = DOM.loginPassword.value;

  if (!email || !password) {
    mostrarAlertaLogin('Por favor completa todos los campos.');
    return;
  }

  setBotonCargando(DOM.btnLoginSubmit, true, 'Verificando...');

  try {
    // Formato OAuth2 Password Flow requerido por FastAPI
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Credenciales incorrectas o usuario no registrado.');
      }
      if (response.status === 429) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Demasiados intentos fallidos. Intente nuevamente más tarde.');
      }
      throw new Error(`Error en el servidor (${response.status})`);
    }

    const data = await response.json();
    const token = data.access_token;

    // 1. Guardar token en estado y en LocalStorage
    state.token = token;
    localStorage.setItem(STORAGE_KEYS.TOKEN, token);

    // 2. Obtener el perfil del usuario autenticado (/usuarios/me)
    await cargarPerfilUsuario();

    // 3. Transicionar a la interfaz principal
    cambiarVista('dashboard');
    showToast(`¡Bienvenido/a, ${state.user ? state.user.nombre : 'Usuario'}!`, 'success');

    // 4. Cargar datos iniciales
    cargarSalas();
    cargarReservas();
  } catch (error) {
    mostrarAlertaLogin(error.message);
  } finally {
    setBotonCargando(DOM.btnLoginSubmit, false, 'Iniciar Sesión');
  }
}

/**
 * Consulta la información del usuario en sesión (/usuarios/me)
 */
async function cargarPerfilUsuario() {
  const response = await apiFetch('/usuarios/me');
  if (response.ok) {
    const user = await response.json();
    state.user = user;
    localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user));
    renderizarNavbarUsuario();
  }
}

/**
 * Actualiza el indicador visual de usuario en el header
 */
function renderizarNavbarUsuario() {
  if (!state.user) return;
  DOM.navUserName.textContent = state.user.nombre;
  DOM.navUserRole.textContent = state.user.rol;
  DOM.navUserRole.setAttribute('data-role', state.user.rol);

  // Mostrar pestaña de administración solo a Admin / Encargado
  const esGestor = state.user.rol === 'Admin' || state.user.rol === 'Encargado';
  DOM.tabAdmin.classList.toggle('hidden', !esGestor);

  // Solo Admin puede crear/eliminar tipos de sala
  DOM.formNuevoTipo.style.display = state.user.rol === 'Admin' ? '' : 'none';
}

/**
 * Cierra la sesión activa y limpia LocalStorage
 */
function cerrarSesion(porExpiracion = false) {
  state.token = null;
  state.user = null;
  state.salas = [];
  state.reservas = [];

  localStorage.removeItem(STORAGE_KEYS.TOKEN);
  localStorage.removeItem(STORAGE_KEYS.USER);

  cambiarVista('login');
  DOM.formLogin.reset();

  if (porExpiracion) {
    mostrarAlertaLogin('Tu sesión ha expirado. Por favor ingresa nuevamente.');
  }
}

function mostrarAlertaLogin(mensaje) {
  DOM.loginAlertMsg.textContent = mensaje;
  DOM.loginAlert.classList.remove('hidden');
}

function ocultarAlertaLogin() {
  DOM.loginAlert.classList.add('hidden');
}

// ----------------------------------------------------------------------------
// 5. MÓDULO DE SALAS (DASHBOARD)
// ----------------------------------------------------------------------------
/**
 * Consulta el listado de salas desde GET /api/salas/
 */
async function cargarSalas() {
  DOM.salasLoading.classList.remove('hidden');
  DOM.salasGrid.classList.add('hidden');
  DOM.salasEmpty.classList.add('hidden');

  try {
    const response = await apiFetch('/salas/?solo_habilitadas=true');
    if (!response.ok) throw new Error('No se pudo cargar la lista de salas');

    const salas = await response.json();
    state.salas = salas;
    renderizarSalas(salas);
  } catch (error) {
    console.error('Error al cargar salas:', error);
    DOM.salasEmpty.classList.remove('hidden');
    DOM.salasEmpty.querySelector('p').textContent = error.message;
  } finally {
    DOM.salasLoading.classList.add('hidden');
  }
}

/**
 * Genera el HTML de las tarjetas de sala
 */
function renderizarSalas(salas) {
  if (!salas || salas.length === 0) {
    DOM.salasGrid.classList.add('hidden');
    DOM.salasEmpty.classList.remove('hidden');
    return;
  }

  DOM.salasEmpty.classList.add('hidden');
  DOM.salasGrid.classList.remove('hidden');

  DOM.salasGrid.innerHTML = salas
    .map(sala => {
      const tipoLegible = obtenerTipoSala(sala.acronimo);
      return `
        <article class="sala-card" data-sala-id="${sala.id}">
          <div>
            <div class="sala-card-top">
              <span class="sala-acronimo-tag">${sala.acronimo}</span>
              <span class="badge-status status-activa">Disponible</span>
            </div>
            <h3 class="sala-card-name">${sala.nombre_completo || `${sala.acronimo}-${sala.numero}`}</h3>
            <p style="font-size: 0.85rem; color: var(--color-text-muted); margin-bottom: 0.8rem;">
              ${tipoLegible}
            </p>
            <div class="sala-meta-list">
              <div class="sala-meta-item">
                <span>👥</span>
                <span>Capacidad: <strong>${sala.capacidad} personas</strong></span>
              </div>
              <div class="sala-meta-item">
                <span>🕒</span>
                <span>Bloques de 45 minutos</span>
              </div>
            </div>
          </div>
          <div class="sala-card-footer">
            <button 
              type="button" 
              class="btn btn-primary btn-block btn-abrir-reserva" 
              data-sala-id="${sala.id}"
            >
              📅 Reservar Sala
            </button>
          </div>
        </article>
      `;
    })
    .join('');

  // Asociar evento a los botones de reservar
  DOM.salasGrid.querySelectorAll('.btn-abrir-reserva').forEach(btn => {
    btn.addEventListener('click', () => {
      const salaId = parseInt(btn.dataset.salaId, 10);
      const sala = state.salas.find(s => s.id === salaId);
      if (sala) {
        abrirModalReserva(sala);
      }
    });
  });
}

function obtenerTipoSala(acronimo) {
  if (state.tiposSala) {
    const t = state.tiposSala.find(t => t.acronimo === acronimo);
    if (t) return t.descripcion;
  }
  const mapa = {
    LAB: 'Laboratorio de Computación / Práctica',
    AUD: 'Auditorio Institucional',
    SALA: 'Sala de Clases Teórica',
    CONF: 'Sala de Conferencias / Reuniones',
  };
  return mapa[acronimo] || 'Espacio Académico';
}

function filtrarSalas() {
  const query = DOM.inputFiltroSala.value.trim().toLowerCase();
  if (!query) {
    renderizarSalas(state.salas);
    return;
  }

  const filtradas = state.salas.filter(s => {
    const nombre = (s.nombre_completo || `${s.acronimo}-${s.numero}`).toLowerCase();
    const acronimo = s.acronimo.toLowerCase();
    return nombre.includes(query) || acronimo.includes(query);
  });

  renderizarSalas(filtradas);
}

// ----------------------------------------------------------------------------
// 6. MODAL DE RESERVA Y CONTROL DE CONCURRENCIA (POST /reservas/)
// ----------------------------------------------------------------------------
/**
 * Abre el modal de reserva inicializando fecha mínima (hoy) y reseteando alertas
 */
function abrirModalReserva(sala) {
  state.salaSeleccionada = sala;

  DOM.reservaSalaId.value = sala.id;
  DOM.modalSalaNombre.textContent = sala.nombre_completo || `${sala.acronimo}-${sala.numero}`;
  DOM.modalSalaCapacidad.textContent = `${sala.capacidad} personas`;

  // Fijar fecha mínima en 'hoy' (formato YYYY-MM-DD) para no permitir reservas pasadas
  const hoyStr = new Date().toISOString().split('T')[0];
  DOM.reservaFecha.min = hoyStr;
  DOM.reservaFecha.value = hoyStr;

  // Resetear alertas
  DOM.modalAlertConflict.classList.add('hidden');
  DOM.modalAlertSuccess.classList.add('hidden');
  DOM.reservaHora.selectedIndex = 0;

  // Mostrar modal
  DOM.modalReserva.classList.remove('hidden');
}

function cerrarModalReserva() {
  DOM.modalReserva.classList.add('hidden');
  DOM.modalAlertConflict.classList.add('hidden');
  DOM.modalAlertSuccess.classList.add('hidden');
  state.salaSeleccionada = null;
}

/**
 * Envío de la reserva al backend con gestión crítica de concurrencia:
 * - Si retorna HTTP 409: Alerta visual roja ("El bloque ya fue reservado...")
 * - Si retorna HTTP 201: Éxito y actualización de datos
 */
async function procesarCreacionReserva(event) {
  event.preventDefault();

  DOM.modalAlertConflict.classList.add('hidden');
  DOM.modalAlertSuccess.classList.add('hidden');

  const id_sala = parseInt(DOM.reservaSalaId.value, 10);
  const fecha = DOM.reservaFecha.value;
  const hora_inicio = DOM.reservaHora.value;
  const bloque_minutos = parseInt(DOM.reservaDuracion.value, 10) || 45;

  if (!fecha || !hora_inicio) {
    showToast('Por favor selecciona la fecha y el horario de inicio', 'error');
    return;
  }

  setBotonCargando(DOM.btnSubmitReserva, true, 'Confirmando...');

  try {
    const payload = {
      id_sala,
      fecha,
      hora_inicio,
      bloque_minutos,
    };

    const response = await apiFetch('/reservas/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    // ------------------------------------------------------------------------
    // GESTIÓN CRÍTICA DE CONCURRENCIA (HTTP 409 CONFLICT)
    // ------------------------------------------------------------------------
    if (response.status === 409) {
      const errorData = await response.json();
      console.warn('[Concurrencia Detectada]:', errorData);

      // Mostrar alerta visual en rojo con el texto exacto requerido
      DOM.modalAlertText.textContent =
        'El bloque ya fue reservado por otro usuario. Por favor, seleccione otro horario.';
      DOM.modalAlertConflict.classList.remove('hidden');
      return;
    }

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      const mensaje = err.detail || `Error al procesar la reserva (${response.status})`;
      throw new Error(mensaje);
    }

    // ÉXITO (HTTP 201 CREATED)
    DOM.modalAlertSuccess.classList.remove('hidden');
    showToast('¡Reserva creada exitosamente!', 'success');

    // Cerrar modal tras breve pausa y refrescar reservas
    setTimeout(() => {
      cerrarModalReserva();
      cargarReservas();
    }, 1200);
  } catch (error) {
    DOM.modalAlertText.textContent = error.message;
    DOM.modalAlertConflict.classList.remove('hidden');
  } finally {
    setBotonCargando(DOM.btnSubmitReserva, false, 'Confirmar Reserva');
  }
}

// ----------------------------------------------------------------------------
// 7. MÓDULO "MIS RESERVAS"
// ----------------------------------------------------------------------------
/**
 * Consulta las reservas del usuario autenticado (GET /api/reservas/)
 */
async function cargarReservas() {
  DOM.reservasLoading.classList.remove('hidden');
  DOM.reservasList.classList.add('hidden');
  DOM.reservasEmpty.classList.add('hidden');

  try {
    const response = await apiFetch('/reservas/');
    if (!response.ok) throw new Error('No se pudieron obtener las reservas');

    const reservas = await response.json();
    state.reservas = reservas;

    // Actualizar badge de reservas activas en el navbar
    const activas = reservas.filter(r => r.estado === 'Activa');
    if (activas.length > 0) {
      DOM.badgeReservasCount.textContent = activas.length;
      DOM.badgeReservasCount.classList.remove('hidden');
    } else {
      DOM.badgeReservasCount.classList.add('hidden');
    }

    renderizarReservas(reservas);
  } catch (error) {
    console.error('Error al cargar reservas:', error);
    DOM.reservasEmpty.classList.remove('hidden');
    DOM.reservasEmpty.querySelector('p').textContent = error.message;
  } finally {
    DOM.reservasLoading.classList.add('hidden');
  }
}

/**
 * Renderiza la lista de reservas
 */
function renderizarReservas(reservas) {
  if (!reservas || reservas.length === 0) {
    DOM.reservasList.classList.add('hidden');
    DOM.reservasEmpty.classList.remove('hidden');
    return;
  }

  DOM.reservasEmpty.classList.add('hidden');
  DOM.reservasList.classList.remove('hidden');

  DOM.reservasList.innerHTML = reservas
    .map(reserva => {
      // Buscar el nombre de la sala en caché local de salas
      const sala = state.salas.find(s => s.id === reserva.id_sala);
      const nombreSala = sala ? sala.nombre_completo : `Sala ID ${reserva.id_sala}`;

      const esActiva = reserva.estado === 'Activa';
      const claseEstado =
        reserva.estado === 'Activa'
          ? 'status-activa'
          : reserva.estado === 'Cancelada'
          ? 'status-cancelada'
          : 'status-asistida';

      return `
        <article class="reserva-item-card" data-reserva-id="${reserva.id}">
          <div style="flex: 1;">
            <div class="reserva-header">
              <h3 class="reserva-sala-title">${nombreSala}</h3>
              <span class="badge-status ${claseEstado}">${reserva.estado}</span>
            </div>

            <div class="reserva-details-grid" style="margin-top: 0.6rem;">
              <div>
                <span class="reserva-meta-label">Fecha</span>
                <span class="reserva-meta-val">${formatearFecha(reserva.fecha)}</span>
              </div>
              <div>
                <span class="reserva-meta-label">Horario de Inicio</span>
                <span class="reserva-meta-val">${reserva.hora_inicio} hrs</span>
              </div>
              <div>
                <span class="reserva-meta-label">Duración</span>
                <span class="reserva-meta-val">${reserva.bloque_minutos} min</span>
              </div>
              <div>
                <span class="reserva-meta-label">N° Reserva</span>
                <span class="reserva-meta-val">#${reserva.id}</span>
              </div>
            </div>
          </div>

          <div class="reserva-actions">
            ${
              esActiva
                ? `
              <button 
                type="button" 
                class="btn btn-danger btn-sm btn-cancelar-reserva" 
                data-reserva-id="${reserva.id}"
              >
                ❌ Cancelar Reserva
              </button>
            `
                : `
              <span style="font-size: 0.8rem; color: var(--color-text-muted); font-style: italic;">
                ${reserva.estado === 'Cancelada' ? 'Cancelada' : 'Finalizada'}
              </span>
            `
            }
          </div>
        </article>
      `;
    })
    .join('');

  // Asociar evento a los botones de cancelar
  DOM.reservasList.querySelectorAll('.btn-cancelar-reserva').forEach(btn => {
    btn.addEventListener('click', () => {
      const reservaId = parseInt(btn.dataset.reservaId, 10);
      cancelarReserva(reservaId);
    });
  });
}

/**
 * Cancela una reserva mediante PATCH /api/reservas/{id}
 */
async function cancelarReserva(reservaId) {
  const confirmacion = confirm(
    '¿Estás seguro de cancelar esta reserva?\nTen en cuenta que esto sumará a tu contador de cancelaciones.'
  );
  if (!confirmacion) return;

  try {
    const response = await apiFetch(`/reservas/${reservaId}`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: 'Cancelada' }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'No se pudo cancelar la reserva.');
    }

    showToast('Reserva cancelada correctamente', 'info');
    // Actualizar listado de reservas
    cargarReservas();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

function formatearFecha(fechaStr) {
  try {
    const partes = fechaStr.split('-');
    if (partes.length === 3) {
      return `${partes[2]}/${partes[1]}/${partes[0]}`;
    }
    return fechaStr;
  } catch {
    return fechaStr;
  }
}

// ----------------------------------------------------------------------------
// 7.5 MÓDULO DE ADMINISTRACIÓN (SALAS + TIPOS)
// ----------------------------------------------------------------------------

/** Carga todas las salas (incluidas las deshabilitadas) para gestión */
async function cargarAdminSalas() {
  try {
    const response = await apiFetch('/salas/?solo_habilitadas=false');
    if (!response.ok) throw new Error('No se pudieron cargar las salas');
    const salas = await response.json();
    state.salasAdmin = salas;
    renderizarAdminSalas(salas);
  } catch (error) {
    showToast(error.message, 'error');
  }
}

function renderizarAdminSalas(salas) {
  if (!salas || salas.length === 0) {
    DOM.adminSalasTbody.innerHTML = '';
    DOM.adminSalasEmpty.classList.remove('hidden');
    return;
  }
  DOM.adminSalasEmpty.classList.add('hidden');

  DOM.adminSalasTbody.innerHTML = salas
    .map(sala => {
      const habilitada = sala.estado_habilitacion;
      const nombre = sala.nombre_completo || `${sala.acronimo}-${sala.numero}`;
      return `
        <tr>
          <td>#${sala.id}</td>
          <td><strong>${nombre}</strong></td>
          <td>${sala.acronimo}</td>
          <td>${sala.capacidad}</td>
          <td>
            <span class="badge-status ${habilitada ? 'status-activa' : 'status-cancelada'}">
              ${habilitada ? 'Habilitada' : 'Deshabilitada'}
            </span>
          </td>
          <td>
            <button type="button" class="btn btn-secondary btn-sm btn-icon-sm btn-editar-sala" data-sala-id="${sala.id}">✏️ Editar</button>
            ${
              habilitada
                ? `<button type="button" class="btn btn-danger btn-sm btn-icon-sm btn-deshabilitar-sala" data-sala-id="${sala.id}">🚫 Deshabilitar</button>`
                : `<button type="button" class="btn btn-primary btn-sm btn-icon-sm btn-habilitar-sala" data-sala-id="${sala.id}">✅ Habilitar</button>`
            }
          </td>
        </tr>
      `;
    })
    .join('');

  DOM.adminSalasTbody.querySelectorAll('.btn-editar-sala').forEach(btn => {
    btn.addEventListener('click', () => {
      const sala = state.salasAdmin.find(s => s.id === parseInt(btn.dataset.salaId, 10));
      if (sala) abrirModalSala(sala);
    });
  });
  DOM.adminSalasTbody.querySelectorAll('.btn-deshabilitar-sala').forEach(btn => {
    btn.addEventListener('click', () => cambiarEstadoSala(parseInt(btn.dataset.salaId, 10), 'deshabilitar'));
  });
  DOM.adminSalasTbody.querySelectorAll('.btn-habilitar-sala').forEach(btn => {
    btn.addEventListener('click', () => cambiarEstadoSala(parseInt(btn.dataset.salaId, 10), 'habilitar'));
  });
}

async function cambiarEstadoSala(salaId, accion) {
  if (!confirm(`¿Seguro que deseas ${accion} la sala #${salaId}?`)) return;
  try {
    const response = await apiFetch(`/salas/${salaId}/${accion}`, { method: 'PATCH' });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `No se pudo ${accion} la sala.`);
    }
    showToast(`Sala ${accion === 'habilitar' ? 'habilitada' : 'deshabilitada'} correctamente`, 'success');
    cargarAdminSalas();
    cargarSalas();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

/** Carga el catálogo de tipos de sala desde el backend */
async function cargarTiposSala() {
  try {
    const response = await apiFetch('/salas/tipos/');
    if (!response.ok) throw new Error('No se pudieron cargar los tipos de sala');
    const tipos = await response.json();
    state.tiposSala = tipos;
    renderizarTiposSala(tipos);
    poblarSelectAcronimos(tipos);
  } catch (error) {
    showToast(error.message, 'error');
  }
}

function renderizarTiposSala(tipos) {
  const esAdmin = state.user && state.user.rol === 'Admin';
  DOM.adminTiposTbody.innerHTML = tipos
    .map(t => `
      <tr>
        <td><strong>${t.acronimo}</strong></td>
        <td>${t.descripcion}</td>
        <td>
          ${esAdmin ? `<button type="button" class="btn btn-danger btn-sm btn-icon-sm btn-eliminar-tipo" data-acronimo="${t.acronimo}">🗑️ Eliminar</button>` : ''}
        </td>
      </tr>
    `)
    .join('');

  DOM.adminTiposTbody.querySelectorAll('.btn-eliminar-tipo').forEach(btn => {
    btn.addEventListener('click', () => eliminarTipoSala(btn.dataset.acronimo));
  });
}

function poblarSelectAcronimos(tipos) {
  DOM.salaAcronimo.innerHTML = tipos
    .map(t => `<option value="${t.acronimo}">${t.acronimo} — ${t.descripcion}</option>`)
    .join('');
}

async function crearTipoSala(event) {
  event.preventDefault();
  const acronimo = DOM.tipoAcronimo.value.trim().toUpperCase();
  const descripcion = DOM.tipoDescripcion.value.trim();

  if (!acronimo || !descripcion) {
    showToast('Completa acrónimo y descripción del tipo.', 'error');
    return;
  }

  try {
    const response = await apiFetch('/salas/tipos/', {
      method: 'POST',
      body: JSON.stringify({ acronimo, descripcion }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'No se pudo crear el tipo de sala.');
    }
    showToast(`Tipo '${acronimo}' creado correctamente`, 'success');
    DOM.formNuevoTipo.reset();
    cargarTiposSala();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

async function eliminarTipoSala(acronimo) {
  if (!confirm(`¿Eliminar el tipo de sala '${acronimo}'?`)) return;
  try {
    const response = await apiFetch(`/salas/tipos/${acronimo}`, { method: 'DELETE' });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'No se pudo eliminar el tipo.');
    }
    showToast(`Tipo '${acronimo}' eliminado`, 'info');
    cargarTiposSala();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

async function abrirModalSala(sala = null) {
  // Asegurar que el catálogo de tipos esté cargado para el select
  if (!state.tiposSala || state.tiposSala.length === 0) {
    await cargarTiposSala();
  }

  DOM.formSala.reset();
  if (sala) {
    DOM.modalSalaTitulo.textContent = `Editar Sala ${sala.nombre_completo || ''}`;
    DOM.salaIdEdit.value = sala.id;
    DOM.salaAcronimo.value = sala.acronimo;
    DOM.salaNumero.value = sala.numero;
    DOM.salaCapacidad.value = sala.capacidad;
    DOM.salaHabilitada.checked = sala.estado_habilitacion;
  } else {
    DOM.modalSalaTitulo.textContent = 'Nueva Sala';
    DOM.salaIdEdit.value = '';
    DOM.salaHabilitada.checked = true;
  }
  DOM.modalSala.classList.remove('hidden');
}

function cerrarModalSala() {
  DOM.modalSala.classList.add('hidden');
  state.salaSeleccionada = null;
}

async function procesarFormSala(event) {
  event.preventDefault();

  const idEdit = DOM.salaIdEdit.value;
  const payload = {
    acronimo: DOM.salaAcronimo.value,
    numero: DOM.salaNumero.value.trim(),
    capacidad: parseInt(DOM.salaCapacidad.value, 10),
    estado_habilitacion: DOM.salaHabilitada.checked,
  };

  if (!payload.acronimo || !payload.numero || !payload.capacidad) {
    showToast('Completa todos los campos de la sala.', 'error');
    return;
  }

  try {
    let response;
    if (idEdit) {
      response = await apiFetch(`/salas/${idEdit}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
    } else {
      response = await apiFetch('/salas/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    }

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'No se pudo guardar la sala.');
    }

    showToast(idEdit ? 'Sala actualizada correctamente' : 'Sala creada correctamente', 'success');
    cerrarModalSala();
    cargarAdminSalas();
    cargarSalas();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

// ----------------------------------------------------------------------------
// 8. TOAST NOTIFICATIONS (MENSAJES FLOTANTES)
// ----------------------------------------------------------------------------
function showToast(mensaje, tipo = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${tipo}`;

  const icono = tipo === 'success' ? '✅' : tipo === 'error' ? '⚠️' : 'ℹ️';
  toast.innerHTML = `<span>${icono}</span> <span>${mensaje}</span>`;

  DOM.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function setBotonCargando(btn, cargando, textoOriginal) {
  const spinner = btn.querySelector('.btn-spinner');
  const textSpan = btn.querySelector('.btn-text');

  if (cargando) {
    btn.disabled = true;
    if (spinner) spinner.classList.remove('hidden');
    if (textSpan) textSpan.textContent = textoOriginal;
  } else {
    btn.disabled = false;
    if (spinner) spinner.classList.add('hidden');
    if (textSpan) textSpan.textContent = textoOriginal;
  }
}

// ----------------------------------------------------------------------------
// 9. INICIALIZACIÓN DE EVENTOS Y ARRANQUE DE LA APP
// ----------------------------------------------------------------------------
function inicializarApp() {
  // 1. Eventos de autenticación
  DOM.formLogin.addEventListener('submit', iniciarSesion);
  DOM.btnLogout.addEventListener('click', () => cerrarSesion(false));

  // 2. Botones de acceso rápido para pruebas académicas (EVA 3)
  document.querySelectorAll('.btn-quick').forEach(btn => {
    btn.addEventListener('click', () => {
      DOM.loginEmail.value = btn.dataset.email;
      DOM.loginPassword.value = 'inacap2026';
      DOM.btnLoginSubmit.focus();
    });
  });

  // 3. Pestañas de navegación
  DOM.tabSalas.addEventListener('click', () => cambiarPestana('panel-salas'));
  DOM.tabReservas.addEventListener('click', () => cambiarPestana('panel-reservas'));
  DOM.tabAdmin.addEventListener('click', () => cambiarPestana('panel-admin'));
  DOM.btnIrASalas.addEventListener('click', () => cambiarPestana('panel-salas'));

  // 3.1 Panel de administración
  DOM.btnNuevaSala.addEventListener('click', () => abrirModalSala(null));
  DOM.btnRefreshAdmin.addEventListener('click', () => { cargarAdminSalas(); cargarTiposSala(); });
  DOM.formNuevoTipo.addEventListener('submit', crearTipoSala);
  DOM.formSala.addEventListener('submit', procesarFormSala);
  DOM.btnCloseModalSala.addEventListener('click', cerrarModalSala);
  DOM.btnCancelarModalSala.addEventListener('click', cerrarModalSala);
  DOM.modalSala.addEventListener('click', e => {
    if (e.target === DOM.modalSala) cerrarModalSala();
  });

  // 4. Refresco manual y buscador de salas
  DOM.btnRefreshSalas.addEventListener('click', cargarSalas);
  DOM.btnRefreshReservas.addEventListener('click', cargarReservas);
  DOM.inputFiltroSala.addEventListener('input', filtrarSalas);

  // 5. Modal de Reserva
  DOM.btnCloseModal.addEventListener('click', cerrarModalReserva);
  DOM.btnCancelarModal.addEventListener('click', cerrarModalReserva);
  DOM.modalReserva.addEventListener('click', e => {
    if (e.target === DOM.modalReserva) cerrarModalReserva();
  });
  DOM.formCrearReserva.addEventListener('submit', procesarCreacionReserva);

  // 6. Verificar si existe sesión previa válida en LocalStorage
  if (state.token) {
    cambiarVista('dashboard');
    renderizarNavbarUsuario();
    cargarSalas();
    cargarReservas();
  } else {
    cambiarVista('login');
  }
}

// Iniciar al cargar el DOM
document.addEventListener('DOMContentLoaded', inicializarApp);

        document.body.classList.add('js-ready');
        document.body.classList.add('auth-locked');
        // ============================================
        // TRADING ASSISTANT — FRONTEND (SPA en español)
        // ============================================
        // Todo el comportamiento de la interfaz se orquesta en este script:
        //
        //   · Autenticación  -> registro/login con token (localStorage), menú de usuario
        //   · Operación      -> selección de par, monto, iniciar/pausar/reiniciar simulación
        //   · Datos          -> cotizaciones en vivo (Yahoo Finance) y tipo de cambio
        //   · Gráfica        -> Chart.js con SMA5/SMA20, zoom/pan y pronóstico ARIMA
        //   · Simulación     -> estrategia SMA crossover con stop-loss, día por tick
        //   · Métricas       -> rendimiento, Sharpe, drawdown, win rate
        //   · Semáforo       -> veredicto combinado 60% noticias/IA + 40% estadística ARMA
        //   · Análisis IA    -> VADER (noticias) + DeepSeek (veredicto razonado)
        //   · Historial      -> comparativa con simulaciones previas guardadas (cifradas)
        //
        // API_BASE: en localhost apunta a http://localhost:8000; en producción usa
        // el mismo origen (mismo dominio que la API).
        // ============================================

        const API_BASE =
            location.hostname === 'localhost' || location.hostname === '127.0.0.1'
                ? 'http://localhost:8000'
                : '';

        function formatearNumero(n, decimals = 2) {
            return n.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        }

        function clampNum(v, min, max) {
            return Math.min(max, Math.max(min, v));
        }

        const SIMBOLOS_MONEDA = {
            'USD': { nombre: 'Dólar', simbolo: '$', bandera: '\uD83C\uDDFA\uD83C\uDDF8' },
            'MXN': { nombre: 'Peso Mexicano', simbolo: '$', bandera: '\uD83C\uDDF2\uD83C\uDDFD' },
            'JPY': { nombre: 'Yen', simbolo: '\u00A5', bandera: '\uD83C\uDDEF\uD83C\uDDF5' },
            'EUR': { nombre: 'Euro', simbolo: '\u20AC', bandera: '\uD83C\uDDEA\uD83C\uDDFA' }
        };
        
        let preciosActuales = { USD: 1.0, MXN: 0, JPY: 0, EUR: 0 };
        let historicoData = [];
        let monedaFrom = 'USD';
        let monedaTo = 'MXN';
        let simulacionActiva = false;
        let intervaloSim = null;
        let diaActual = 0;
        let historialSenales = [];
        let maxCapitalSim = 0;
        let graficoGrande = null;
        let ultimoPronostico = null;
        let senalNoticias = null;
        let senalEstadistica = null;
        let graficoSource = [];
        let graficoOffset = 0;
        let graficoLen = 1; // 1 = mostrar todo el historico; >2 = ventana con zoom
        
        document.addEventListener('DOMContentLoaded', () => {
            inicializarAuth();
            verificarSesion();
        });

        // ========== AUTENTICACIÓN ==========
        const TOKEN_KEY = 'trading_assistant_token';

        function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
        function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }

        function inicializarAuth() {
            const authScreen = document.getElementById('authScreen');
            const welcome = document.getElementById('authWelcome');
            const loginForm = document.getElementById('loginForm');
            const registerForm = document.getElementById('registerForm');
            const loginError = document.getElementById('authError');
            const registerError = document.getElementById('regError');

            const mostrarVista = (ocultar, mostrar) => {
                ocultar.style.display = 'none';
                mostrar.style.display = 'flex';
                mostrar.style.animation = 'none';
                void mostrar.offsetWidth;
                mostrar.style.animation = '';
            };
            const volverInicio = (e) => {
                e.preventDefault();
                loginForm.style.display = 'none';
                registerForm.style.display = 'none';
                loginError.textContent = '';
                registerError.textContent = '';
                welcome.style.display = 'flex';
                welcome.style.animation = 'none';
                void welcome.offsetWidth;
                welcome.style.animation = '';
            };

            document.getElementById('btnShowLogin').addEventListener('click', () => {
                loginError.textContent = '';
                registerError.textContent = '';
                mostrarVista(welcome, loginForm);
            });
            document.getElementById('btnShowRegister').addEventListener('click', () => {
                loginError.textContent = '';
                registerError.textContent = '';
                mostrarVista(welcome, registerForm);
            });
            document.querySelectorAll('.auth-back').forEach(link => {
                link.addEventListener('click', volverInicio);
            });

            document.querySelectorAll('.auth-toggle').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const input = document.getElementById(btn.dataset.target);
                    if (!input) return;
                    const mostrar = input.type === 'password';
                    input.type = mostrar ? 'text' : 'password';
                    btn.innerHTML = mostrar ? '<i class="fas fa-eye-slash"></i>' : '<i class="fas fa-eye"></i>';
                    input.value = input.value;
                    input.focus();
                });
            });

            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const username = document.getElementById('loginUsername').value.trim();
                const password = document.getElementById('loginPassword').value;
                const errorEl = loginError;
                errorEl.textContent = '';
                if (!username || !password) {
                    errorEl.textContent = 'Ingresa usuario y contraseña';
                    return;
                }
                try {
                    const resp = await fetch(`${API_BASE}/api/auth/login`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username, password }),
                    });
                    const data = await resp.json();
                    if (data.success) {
                        setToken(data.token);
                        iniciarApp(data.username, false);
                    } else {
                        errorEl.textContent = data.error || 'Error al iniciar sesión';
                    }
                } catch (err) {
                    errorEl.textContent = 'No se pudo conectar con el servidor';
                }
            });

            registerForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const username = document.getElementById('regUsername').value.trim();
                const password = document.getElementById('regPassword').value;
                const errorEl = registerError;
                errorEl.textContent = '';
                if (!username || !password) {
                    errorEl.textContent = 'Ingresa usuario y contraseña';
                    return;
                }
                if (password.length < 8 || !/[A-Z]/.test(password) || !/[0-9]/.test(password) || !/[^A-Za-z0-9]/.test(password)) {
                    errorEl.textContent = 'La contraseña debe tener mínimo 8 caracteres, con al menos una mayúscula, un número y un carácter especial';
                    return;
                }
                registroPendiente = { username, password };
                mostrarTerminos('registro');
            });

            // ===== TÉRMINOS Y CONDICIONES =====
            let registroPendiente = null;
            let terminosModo = 'registro'; // 'registro' | 'vista'
            const termsScreen = document.getElementById('termsScreen');
            const termsCheck = document.getElementById('termsCheck');
            const termsError = document.getElementById('termsError');
            const termsAcceptWrap = termsCheck.closest('.terms-accept');
            const btnTermsAceptar = document.getElementById('btnTermsAceptar');
            const btnTermsCancelar = document.getElementById('btnTermsCancelar');
            const btnTermsClose = document.getElementById('btnTermsClose');
            const termsSubtitle = document.getElementById('termsSubtitle');

            function mostrarTerminos(modo) {
                const vista = modo === 'vista';
                terminosModo = vista ? 'vista' : 'registro';
                registerForm.style.display = 'none';
                authScreen.style.display = 'none';
                termsScreen.style.display = 'flex';
                termsCheck.checked = false;
                termsError.textContent = '';
                termsSubtitle.textContent = vista ? 'Información legal y de privacidad' : 'Debes aceptarlos para crear tu cuenta';
                termsAcceptWrap.style.display = vista ? 'none' : 'flex';
                btnTermsAceptar.style.display = vista ? 'none' : 'flex';
                btnTermsCancelar.style.display = vista ? 'none' : 'flex';
                btnTermsClose.style.display = vista ? 'flex' : 'none';
                document.body.classList.add('auth-locked');
                if (!vista) btnTermsAceptar.disabled = true;
            }

            function volverLogin() {
                termsScreen.style.display = 'none';
                authScreen.style.display = 'flex';
                welcome.style.display = 'none';
                registerForm.style.display = 'none';
                loginForm.style.display = 'flex';
                registerError.textContent = '';
            }

            function cerrarTerminosVista() {
                termsScreen.style.display = 'none';
                document.body.classList.remove('auth-locked');
            }

            termsCheck.addEventListener('change', () => {
                btnTermsAceptar.disabled = !termsCheck.checked;
                termsError.textContent = '';
            });

            btnTermsCancelar.addEventListener('click', () => {
                registroPendiente = null;
                volverLogin();
            });

            btnTermsClose.addEventListener('click', cerrarTerminosVista);

            btnTermsAceptar.addEventListener('click', async () => {
                if (!termsCheck.checked) {
                    termsError.textContent = 'Debes aceptar los términos y condiciones para continuar';
                    return;
                }
                if (!registroPendiente) return;
                btnTermsAceptar.disabled = true;
                try {
                    const resp = await fetch(`${API_BASE}/api/auth/register`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(registroPendiente),
                    });
                    const data = await resp.json();
                    if (data.success) {
                        setToken(data.token);
                        termsScreen.style.display = 'none';
                        registroPendiente = null;
                        iniciarApp(data.username, true);
                    } else {
                        termsError.textContent = data.error || 'Error al registrar';
                        btnTermsAceptar.disabled = false;
                    }
                } catch (err) {
                    termsError.textContent = 'No se pudo conectar con el servidor';
                    btnTermsAceptar.disabled = false;
                }
            });

            // Menú de usuario desplegable
            const userBar = document.getElementById('userBar');
            const userMenu = document.getElementById('userMenu');
            const userTrigger = document.getElementById('userTrigger');

            const cerrarMenuUsuario = () => {
                userMenu.style.display = 'none';
                userTrigger.setAttribute('aria-expanded', 'false');
                userBar.classList.remove('open');
            };

            userTrigger.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const abierto = userMenu.style.display === 'block';
                if (abierto) {
                    cerrarMenuUsuario();
                } else {
                    userMenu.style.display = 'block';
                    userTrigger.setAttribute('aria-expanded', 'true');
                    userBar.classList.add('open');
                }
            });

            document.addEventListener('click', (e) => {
                if (!userBar.contains(e.target)) cerrarMenuUsuario();
            });

            async function cerrarSesionCompleta() {
                const token = getToken();
                try {
                    await fetch(`${API_BASE}/api/auth/logout?token=${token}`);
                } catch (err) {}
                localStorage.removeItem(TOKEN_KEY);
                cerrarMenuUsuario();
                mostrarAuth();
            }

            document.getElementById('btnLogout').addEventListener('click', (e) => {
                e.preventDefault();
                cerrarSesionCompleta();
            });

            document.getElementById('btnSwitchUser').addEventListener('click', (e) => {
                e.preventDefault();
                cerrarSesionCompleta();
            });

            document.getElementById('btnShowTerms').addEventListener('click', (e) => {
                e.preventDefault();
                cerrarMenuUsuario();
                mostrarTerminos('vista');
            });

            // Terminar sesión al cerrar la página (pestaña/ventana/recarga)
            window.addEventListener('pagehide', () => {
                const token = getToken();
                localStorage.removeItem(TOKEN_KEY);
                if (token) {
                    try {
                        navigator.sendBeacon(`${API_BASE}/api/auth/logout?token=${encodeURIComponent(token)}`);
                    } catch (err) {}
                }
            });
            window.addEventListener('pageshow', (e) => {
                if (e.persisted) verificarSesion();
            });

            document.getElementById('btnEmpezar').addEventListener('click', comenzarOperaciones);
        }

        function iniciarApp(username, esNuevo) {
            document.getElementById('authScreen').style.display = 'none';
            document.getElementById('userBar').style.display = 'flex';
            document.getElementById('usernameDisplay').textContent = username;
            mostrarBienvenida(username, esNuevo);
        }

        function mostrarBienvenida(username, esNuevo) {
            const titulo = document.getElementById('welcomeTitle');
            const texto = document.getElementById('welcomeTexto');
            if (esNuevo) {
                titulo.textContent = 'Tu próxima operación empieza aquí.';
                texto.textContent = 'Trading Assistant es tu centro de operaciones financieras. Simula inversiones en divisas y acciones, sigue los precios en tiempo real y recibe un análisis automático basado en noticias y una inteligencia artificial que te dice dónde conviene invertir y con qué margen de ganancia. Aprende a operar sin arriesgar tu dinero.';
                texto.style.display = 'block';
            } else {
                titulo.textContent = `Bienvenido, ${username}`;
                texto.style.display = 'none';
            }
            document.getElementById('welcomeScreen').style.display = 'flex';
            document.body.classList.add('auth-locked');
            document.getElementById('btnEmpezar').focus();
        }

        function comenzarOperaciones() {
            document.getElementById('welcomeScreen').style.display = 'none';
            document.body.classList.remove('auth-locked');
            inicializarReveal();
            inicializarEventos();
            verificarBackend();
            cargarPrecios();
            cargarPar();
            cargarComparativa();
        }

        // ========== HISTORIAL (SOLO BASE DE DATOS) ==========
        let simulacionGuardada = false;

        function resetearGuardado() {
            simulacionGuardada = false;
        }

        async function guardarSimulacion(datos) {
            if (simulacionGuardada) return;
            simulacionGuardada = true;
            try {
                const resp = await fetch(`${API_BASE}/api/simulaciones`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: getToken(), ...datos }),
                });
                const data = await resp.json();
            } catch (err) {
                console.log('Error guardando simulacion:', err);
            }
        }

        // ========== COMPARATIVA DE INVERSIÓN (historial previo vs actual) ==========
        let historialSims = [];
        let simActualDatos = null;

        function escapeHtml(str) {
            return String(str).replace(/[&<>"']/g, (c) => {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
        }

        function fmtComp(v) {
            return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }

        function fmtCompSigned(v) {
            return (v >= 0 ? '+' : '') + fmtComp(v);
        }

        function claseRend(v) {
            return v >= 0.05 ? 'verde' : (v <= -0.05 ? 'rojo' : 'amarillo');
        }

        async function cargarComparativa() {
            const token = getToken();
            if (!token) return;
            try {
                const resp = await fetch(`${API_BASE}/api/simulaciones?token=${encodeURIComponent(token)}`);
                const data = await resp.json();
                if (data.success && Array.isArray(data.simulaciones)) {
                    historialSims = data.simulaciones;
                }
            } catch (e) {
                console.log('Error cargando comparativa:', e);
            }
            renderizarComparativa();
        }

        function renderizarComparativa() {
            const countEl = document.getElementById('compHistorialCount');
            const promEl = document.getElementById('compHistorialPromedio');
            const mejorRend = document.getElementById('compMejorRend');
            const mejorDet = document.getElementById('compMejorDet');
            const actualRend = document.getElementById('compActualRend');
            const actualDet = document.getElementById('compActualDet');

            const rends = historialSims.filter(s => typeof s.rendimiento === 'number' && isFinite(s.rendimiento));

            if (countEl) countEl.textContent = historialSims.length;
            if (rends.length) {
                const prom = rends.reduce((a, b) => a + b.rendimiento, 0) / rends.length;
                promEl.innerHTML = `Rendimiento promedio <strong class="${claseRend(prom)}">${fmtCompSigned(prom)}%</strong>`;
            } else {
                promEl.innerHTML = 'Sin simulaciones guardadas';
            }

            let best = null;
            for (const s of historialSims) {
                if (typeof s.rendimiento === 'number' && isFinite(s.rendimiento) &&
                    (!best || s.rendimiento > best.rendimiento)) best = s;
            }
            if (best) {
                mejorRend.textContent = fmtCompSigned(best.rendimiento) + '%';
                mejorRend.className = 'comp-value ' + claseRend(best.rendimiento);
                mejorDet.textContent = `${escapeHtml(best.moneda || '')} · ${escapeHtml(best.recomendacion || '')}`;
            } else {
                mejorRend.textContent = '—';
                mejorRend.className = 'comp-value';
                mejorDet.textContent = '';
            }

            if (simActualDatos) {
                const r = simActualDatos.rendimiento;
                actualRend.textContent = fmtCompSigned(r) + '%';
                actualRend.className = 'comp-value ' + claseRend(r);
                actualDet.textContent = `${escapeHtml(simActualDatos.moneda || '')} · Monto ${fmtComp(simActualDatos.monto || 0)}`;
            } else {
                actualRend.textContent = '—';
                actualRend.className = 'comp-value';
                actualDet.textContent = 'Inicia una simulación';
            }

            renderComparativaTabla();
            actualizarDiferencia();
        }

        function claseSharpe(v) {
            return v >= 1 ? 'verde' : (v >= 0 ? 'amarillo' : 'rojo');
        }

        function claseRec(r) {
            const u = String(r || '').toUpperCase();
            return u === 'COMPRAR' ? 'verde' : (u === 'VENDER' ? 'rojo' : 'amarillo');
        }

        function renderComparativaTabla() {
            const head = document.getElementById('compVsHead');
            const body = document.getElementById('compVsBody');
            const tabla = document.getElementById('compVsTabla');
            const empty = document.getElementById('compVsEmpty');
            if (!head || !body || !tabla || !empty) return;

            const cols = [];
            if (simActualDatos && simActualDatos.monto > 0) {
                cols.push({ tipo: 'actual', datos: simActualDatos });
            }
            let yaDuplicada = false;
            for (const s of historialSims) {
                if (cols.length >= 7) break;
                if (s) {
                    if (!yaDuplicada && simActualDatos &&
                        s.moneda === simActualDatos.moneda &&
                        Math.abs((s.rendimiento || 0) - (simActualDatos.rendimiento || 0)) < 0.0001 &&
                        Math.abs((s.monto || 0) - (simActualDatos.monto || 0)) < 0.0001) {
                        yaDuplicada = true;
                        continue;
                    }
                    cols.push({ tipo: 'hist', datos: s });
                }
            }

            if (!cols.length) {
                tabla.style.display = 'none';
                empty.style.display = 'block';
                return;
            }
            tabla.style.display = 'table';
            empty.style.display = 'none';

            let thead = '<th class="comp-concepto-th">Concepto</th>';
            cols.forEach((c, i) => {
                const etiqueta = c.tipo === 'actual' ? 'ACTUAL' : `Sim ${i}`;
                thead += `<th class="${c.tipo === 'actual' ? 'comp-th-actual' : ''}">${etiqueta}</th>`;
            });
            head.innerHTML = thead;

            const simboloDe = (d) => {
                const to = (d.moneda || '').split('/')[1];
                return (SIMBOLOS_MONEDA[to] || {}).simbolo || '$';
            };
            const numD = (v) => (typeof v === 'number' && isFinite(v)) ? fmtComp(v) : '—';
            const pctD = (v) => (typeof v === 'number' && isFinite(v)) ? `${fmtCompSigned(v)}%` : '—';

            const filas = [
                ['Par', (d) => escapeHtml(d.moneda || '—')],
                ['Monto', (d) => `${simboloDe(d)}${numD(d.monto)}`],
                ['Capital inicial', (d) => `${simboloDe(d)}${numD(d.capital_inicial)}`],
                ['Capital final', (d) => `${simboloDe(d)}${numD(d.capital_final)}`],
                ['Rendimiento', (d) => `<span class="${claseRend(d.rendimiento || 0)}">${pctD(d.rendimiento)}</span>`],
                ['Generado', (d) => `<span class="${(d.generado || 0) >= 0 ? 'verde' : 'rojo'}">${simboloDe(d)}${fmtCompSigned(d.generado || 0)}</span>`],
                ['Sharpe', (d) => `<span class="${claseSharpe(d.sharpe || 0)}">${typeof d.sharpe === 'number' ? d.sharpe.toFixed(2) : '—'}</span>`],
                ['Drawdown', (d) => typeof d.drawdown === 'number' ? `${fmtComp(-Math.abs(d.drawdown))}%` : '—'],
                ['Win rate', (d) => typeof d.win_rate === 'number' ? `${fmtComp(d.win_rate)}%` : '—'],
                ['Recomendación', (d) => d.recomendacion ? `<span class="${claseRec(d.recomendacion)}">${escapeHtml(d.recomendacion)}</span>` : '—'],
            ];
            let bodyHtml = '';
            filas.forEach(([concepto, fn]) => {
                bodyHtml += `<tr><td class="comp-concepto-th">${concepto}</td>`;
                cols.forEach(c => {
                    bodyHtml += `<td class="${c.tipo === 'actual' ? 'comp-td-actual' : ''}">${fn(c.datos)}</td>`;
                });
                bodyHtml += '</tr>';
            });
            body.innerHTML = bodyHtml;
            generarNotaComparativa(cols);
        }

        function generarNotaComparativa(cols) {
            const notaEl = document.getElementById('compVsNota');
            if (!notaEl) return;

            const para = (v) => (typeof v === 'number' && isFinite(v)) ? v : null;
            const hist = cols.filter(c => c.tipo === 'hist').map(c => c.datos);
            const actual = cols.find(c => c.tipo === 'actual');
            const a = actual ? actual.datos : null;

            const partes = [];
            const rends = hist.map(s => para(s.rendimiento)).filter(v => v !== null);

            if (a) {
                const rAct = para(a.rendimiento);
                const rendNombre = a.moneda || 'la simulación';
                if (rAct !== null && rends.length) {
                    const prom = rends.reduce((x, y) => x + y, 0) / rends.length;
                    if (Math.abs(rAct - prom) < 0.01) {
                        partes.push(`Tu simulación actual de <strong>${escapeHtml(rendNombre)}</strong> rindió <strong>${fmtCompSigned(rAct)}%</strong>, prácticamente igual al promedio histórico de <strong>${fmtCompSigned(prom)}%</strong> (${hist.length} sesiones previas).`);
                    } else if (rAct > prom) {
                        partes.push(`Superaste tu promedio histórico: <strong>${fmtCompSigned(rAct)}%</strong> actual vs <strong>${fmtCompSigned(prom)}%</strong> de promedio (${hist.length} sesiones previas).`);
                    } else {
                        partes.push(`Tu simulación actual (<strong>${fmtCompSigned(rAct)}%</strong>) quedó por debajo del promedio histórico de <strong>${fmtCompSigned(prom)}%</strong> (${hist.length} sesiones previas).`);
                    }
                } else if (rAct !== null) {
                    partes.push(`Esta es la <strong>primera simulación guardada</strong> de <strong>${esc(rendNombre)}</strong> con <strong>${fmtCompSigned(rAct)}%</strong> de rendimiento. Guarda más sessions para comparar.`);
                }
            }

            const barreras = hist.concat(a ? [a] : []).filter(s => para(s.rendimiento) !== null);
            if (barreras.length) {
                const mejor = barreras.reduce((x, y) => (para(y.rendimiento) > para(x.rendimiento) ? y : x));
                const mejorV = para(mejor.rendimiento);
                const peor = barreras.reduce((x, y) => (para(y.rendimiento) < para(x.rendimiento) ? y : x));
                const peorV = para(peor.rendimiento);
                const md = mejor.moneda || '—';
                if (mejorV >= 5) {
                    partes.push(`La mejor sesión fue <strong>${esc(md)}</strong> con <strong>${fmtCompSigned(mejorV)}%</strong>; la peor fue <strong>${esc(peor.moneda || '—')}</strong> con <strong>${fmtCompSigned(peorV)}%</strong>.`);
                } else {
                    partes.push(`Rango de rendimiento entre <strong>${fmtCompSigned(peorV)}%</strong> (peor: ${esc(peor.moneda || '—')}) y <strong>${fmtCompSigned(mejorV)}%</strong> (mejor: ${esc(md)}).`);
                }
            }

            const sharps = barreras.map(s => para(s.sharpe)).filter(v => v !== null);
            if (sharps.length) {
                const promS = sharps.reduce((x, y) => x + y, 0) / sharps.length;
                if (promS >= 1) partes.push(`Consistencia saludable: el <strong>Sharpe promedio</strong> es <strong>${promS.toFixed(2)}</strong>, señal de buen retorno ajustado a riesgo.`);
                else if (promS >= 0) partes.push(`El <strong>Sharpe promedio</strong> es <strong>${promS.toFixed(2)}</strong>: los retornos apenas compensan el riesgo asumido.`);
                else partes.push(`Atención: el <strong>Sharpe promedio</strong> es negativo (<strong>${promS.toFixed(2)}</strong>), el riesgo supera los retornos.`);
            }

            const dds = barreras.map(s => para(s.drawdown)).filter(v => v !== null);
            if (dds.length) {
                const maxDD = Math.max(...dds.map(Math.abs));
                const ddS = maxDD * 100;
                if (ddS < 3) partes.push(`Además, la mayor caída del capital fue solo de <strong>${ddS.toFixed(1)}%</strong>: buena gestión del riesgo.`);
                else if (ddS < 10) partes.push(`La mayor caída del capital fue de <strong>${ddS.toFixed(1)}%</strong>: riesgo moderado.`);
                else partes.push(`Ojo: la mayor caída del capital llegó al <strong>${ddS.toFixed(1)}%</strong>: alto riesgo de pérdidas.`);
            }

            if (!partes.length) {
                notaEl.innerHTML = 'Completa tus simulaciones para obtener una explicación basada en los datos de la tabla.';
            } else {
                notaEl.innerHTML = partes.slice(0, 3).join(' ');
            }
        }

        function esc(v) {
            return String(v).replace(/[&<>"']/g, (c) => {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
        }

        function registrarSimulacionActual(datos) {
            if (!datos) return;
            simActualDatos = {
                moneda: datos.moneda,
                monto: datos.monto,
                capital_inicial: datos.capital_inicial,
                capital_final: datos.capital_final,
                rendimiento: datos.rendimiento,
                generado: datos.generado,
                sharpe: datos.sharpe,
                drawdown: datos.drawdown,
                win_rate: datos.win_rate,
                recomendacion: datos.recomendacion,
            };
            renderizarComparativa();
            cargarComparativa();
        }

        function actualizarDiferencia() {
            const box = document.getElementById('compDiferencia');
            if (!box) return;
            if (!simActualDatos) {
                box.style.display = 'none';
                return;
            }
            const rends = historialSims.filter(s => typeof s.rendimiento === 'number' && isFinite(s.rendimiento));
            const prom = rends.length ? rends.reduce((a, b) => a + b.rendimiento, 0) / rends.length : null;
            const r = simActualDatos.rendimiento;
            let html = '';
            if (prom !== null) {
                const diff = r - prom;
                html = `Tu simulación actual rindió <strong>${fmtCompSigned(r)}%</strong> frente a un promedio histórico de <strong>${fmtCompSigned(prom)}%</strong>`;
                if (Math.abs(diff) >= 0.01) html += ` (diferencia <strong>${fmtCompSigned(diff)} p.p.</strong>)`;
                html += '.';
            } else {
                html = `Simulación actual: <strong>${fmtCompSigned(r)}%</strong>. Completa más simulaciones para comparar con tu historial.`;
            }
            box.innerHTML = `<i class="fas fa-chart-line"></i> ${html}`;
            box.style.display = 'block';
        }

        function mostrarAuth() {
            document.getElementById('authScreen').style.display = 'flex';
            document.body.classList.add('auth-locked');
            document.getElementById('userBar').style.display = 'none';
            document.getElementById('authWelcome').style.display = 'flex';
            document.getElementById('loginForm').style.display = 'none';
            document.getElementById('registerForm').style.display = 'none';
            document.getElementById('authError').textContent = '';
            document.getElementById('regError').textContent = '';
        }

        async function verificarSesion() {
            const token = getToken();
            if (!token) { mostrarAuth(); return; }
            try {
                const resp = await fetch(`${API_BASE}/api/auth/me?token=${token}`);
                const data = await resp.json();
                if (data.success) {
                    iniciarApp(data.username, false);
                } else {
                    localStorage.removeItem(TOKEN_KEY);
                    mostrarAuth();
                }
            } catch (err) {
                mostrarAuth();
            }
        }

        // ========== SCROLL REVEAL: cada bloque aparece al hacer scroll ==========
        function inicializarReveal() {
            const bloques = document.querySelectorAll('.bloque');
            if ('IntersectionObserver' in window) {
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('visible');
                            observer.unobserve(entry.target);
                        }
                    });
                }, { threshold: 0.1 });
                bloques.forEach(b => observer.observe(b));
            } else {
                bloques.forEach(b => b.classList.add('visible'));
            }
        }
        
        function inicializarEventos() {
            document.getElementById('btnIniciar').addEventListener('click', iniciarSimulacion);
            document.getElementById('btnPausar').addEventListener('click', pausarSimulacion);
            document.getElementById('btnReiniciar').addEventListener('click', reiniciarSimulacion);
            
            document.getElementById('monedaFrom').addEventListener('change', () => {
                monedaFrom = document.getElementById('monedaFrom').value;
                graficoOffset = 0;
                graficoLen = 1;
                cargarPar();
                reiniciarSimulacion();
            });
            document.getElementById('monedaTo').addEventListener('change', () => {
                monedaTo = document.getElementById('monedaTo').value;
                graficoOffset = 0;
                graficoLen = 1;
                cargarPar();
                reiniciarSimulacion();
            });
            document.getElementById('montoInvertir').addEventListener('input', () => {
                cargarPar();
            });
        }

        // ========== DATOS EN VIVO Y GRÁFICA ==========
        // cargarPrecios / cargarPar: consultan cotizaciones y el par seleccionado.
        // dibujarGraficoGrande: dibuja precio + SMA5/SMA20 con Chart.js.
        // graficoZoom / redibujarGrafico: controlan zoom y panorama de la gráfica.
        
        async function cargarPrecios() {
            try {
                const resp = await fetch(`${API_BASE}/api/precios`);
                const data = await resp.json();
                if (data.monedas) {
                    for (const [moneda, info] of Object.entries(data.monedas)) {
                        preciosActuales[moneda] = info.precio;
                    }
                }
                if (data.timestamp) {
                    const ts = new Date(data.timestamp);
                }
            } catch (e) {
                console.log('Error cargando precios:', e);
            }
        }
        
        async function cargarPar() {
            try {
                const resp = await fetch(`${API_BASE}/api/par/${monedaFrom}/${monedaTo}`);
                const data = await resp.json();
                if (data.rate) {
                    const infoFrom = SIMBOLOS_MONEDA[monedaFrom];
                    const infoTo = SIMBOLOS_MONEDA[monedaTo];
                    const montoEl = document.getElementById('montoInvertir');
                    const montoTexto = montoEl && montoEl.value && montoEl.value.trim() !== '' ? montoEl.value : '';
                    const monto = parseFloat(montoTexto);
                    if (!isNaN(monto) && monto > 0) {
                        const convertido = monto * data.rate;
                        document.getElementById('cambioDisplay').textContent = `${formatearNumero(convertido)} ${monedaTo}`;
                        document.getElementById('cambioDisplay').className = 'chart-stat-value';
                    } else {
                        document.getElementById('cambioDisplay').textContent = `—`;
                        document.getElementById('cambioDisplay').className = 'chart-stat-value';
                    }
                    cargarGraficoGrande();
                }
            } catch (e) {
                console.log('Error cargando par:', e);
            }
        }
        
        function dibujarGraficoGrande(precios, limite) {
            if (typeof Chart === 'undefined') return;
            const container = document.getElementById('graficoContainer');
            if (!container || !precios || precios.length < 2) return;
            container.style.display = 'block';
            inicializarInteraccionesGrafico();

            graficoSource = precios;
            const total = precios.length;

            let from = 0;
            let to = total;
            if (limite !== undefined) {
                graficoOffset = 0;
                graficoLen = 1;
                to = Math.min(Math.max(limite, 2), total);
                from = 0;
            } else if (graficoLen > 2) {
                from = clampNum(graficoOffset, 0, Math.max(0, total - graficoLen));
                to = Math.min(from + graficoLen, total);
            }

            const vis = precios.slice(from, to);
            if (vis.length < 2) return;
            const valores = vis.map(d => typeof d === 'number' ? d : d.precio);
            const etiquetas = vis.map((d, i) => `D${from + i + 1}`);

            const sma = (data, periodo) => {
                const out = [];
                for (let i = 0; i < data.length; i++) {
                    if (i < periodo - 1) { out.push(null); continue; }
                    let sum = 0;
                    for (let j = i - periodo + 1; j <= i; j++) sum += data[j];
                    out.push(+(sum / periodo).toFixed(5));
                }
                return out;
            };

            const seriePrecio = valores;
            const serieSma5 = sma(valores, 5);
            const serieSma20 = sma(valores, 20);

            const ctx = document.getElementById('graficoGrande').getContext('2d');

            if (graficoGrande) {
                graficoGrande.data.labels = etiquetas;
                graficoGrande.data.datasets = graficoGrande.data.datasets.slice(0, 3);
                graficoGrande.data.datasets.forEach((ds, i) => {
                    if (i === 0) ds.label = `${monedaFrom}/${monedaTo}`;
                });
                graficoGrande.data.datasets[0].data = seriePrecio;
                graficoGrande.data.datasets[1].data = serieSma5;
                graficoGrande.data.datasets[2].data = serieSma20;
                graficoGrande.update('none');
                if (to === total && ultimoPronostico) {
                    aplicarPronostico(ultimoPronostico);
                    mostrarSenalEstadistica(ultimoPronostico.senal_estadistica);
                }
                return;
            }

            graficoGrande = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: etiquetas,
                    datasets: [
                        {
                            label: `${monedaFrom}/${monedaTo}`,
                            data: seriePrecio,
                            borderColor: '#00ff88',
                            backgroundColor: 'rgba(0,255,136,0.08)',
                            borderWidth: 2,
                            pointRadius: 0,
                            tension: 0.2,
                            fill: true,
                            spanGaps: false,
                        },
                        {
                            label: 'SMA5',
                            data: serieSma5,
                            borderColor: '#4488ff',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            tension: 0.2,
                            spanGaps: false,
                        },
                        {
                            label: 'SMA20',
                            data: serieSma20,
                            borderColor: '#ffaa00',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            tension: 0.2,
                            spanGaps: false,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    resizeDelay: 0,
                    animation: { duration: 0 },
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                            labels: { color: 'rgba(255,255,255,0.85)', boxWidth: 14, boxHeight: 10, padding: 12, font: { size: 11 } }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(20,24,27,0.95)',
                            titleColor: '#fff',
                            bodyColor: 'rgba(255,255,255,0.85)',
                            borderColor: 'rgba(255,255,255,0.15)',
                            borderWidth: 1,
                            callbacks: {
                                label: (c) => c.dataset.label + ': ' + (c.parsed.y !== null ? c.parsed.y.toFixed(5) : '—'),
                            },
                        },
                    },
                    scales: {
                        x: {
                            ticks: { color: 'rgba(255,255,255,0.45)', maxTicksLimit: 14, font: { size: 10 } },
                            grid: { color: 'rgba(255,255,255,0.05)' },
                        },
                        y: {
                            ticks: { color: 'rgba(255,255,255,0.45)', font: { size: 10 }, callback: (v) => v.toFixed(4) },
                            grid: { color: 'rgba(255,255,255,0.08)' },
                        },
                    },
                },
            });
        }

        function graficoZoom(factor) {
            const total = graficoSource.length;
            if (total < 5) return;
            const actual = graficoLen > 2 ? graficoLen : total;
            const len = clampNum(Math.round(actual * factor), 5, total);
            const mid = graficoOffset + actual / 2;
            graficoOffset = clampNum(Math.round(mid - len / 2), 0, Math.max(0, total - len));
            graficoLen = len;
            redibujarGrafico();
        }

        function redibujarGrafico() {
            if (graficoSource.length) dibujarGraficoGrande(graficoSource);
        }

        function inicializarInteraccionesGrafico() {
            const container = document.getElementById('graficoContainer');
            if (!container || container.dataset.zoomInit) return;
            container.dataset.zoomInit = '1';
            const canvas = document.getElementById('graficoGrande');
            if (!canvas) return;

            canvas.addEventListener('wheel', (e) => {
                e.preventDefault();
                graficoZoom(e.deltaY < 0 ? 0.85 : 1.18);
            }, { passive: false });

            let arrastrando = null;
            canvas.addEventListener('pointerdown', (e) => {
                arrastrando = { x: e.clientX, offset: graficoOffset };
                canvas.setPointerCapture(e.pointerId);
                canvas.classList.add('panning');
            });
            canvas.addEventListener('pointermove', (e) => {
                if (!arrastrando || graficoLen <= 2) return;
                const total = graficoSource.length;
                const vis = Math.min(graficoLen, total);
                const rect = canvas.getBoundingClientRect();
                const diasPixel = vis / rect.width;
                const deltaDias = Math.round((arrastrando.x - e.clientX) * diasPixel);
                graficoOffset = clampNum(arrastrando.offset + deltaDias, 0, Math.max(0, total - vis));
                redibujarGrafico();
            });
            const finArrastre = () => {
                if (arrastrando) {
                    arrastrando = null;
                    canvas.classList.remove('panning');
                }
            };
            canvas.addEventListener('pointerup', finArrastre);
            canvas.addEventListener('pointercancel', finArrastre);
        }

        function aplicarPronostico(pron) {
            if (!graficoGrande || !pron || !pron.pronostico || pron.pronostico.length === 0) return;
            const n = graficoGrande.data.labels.length;
            const nulos = Array(n).fill(null);
            const pad = (arr) => nulos.concat(arr);
            for (let i = 0; i < pron.pronostico.length; i++) {
                graficoGrande.data.labels.push(`F${i + 1}`);
            }
            graficoGrande.data.datasets = graficoGrande.data.datasets.slice(0, 3);
            graficoGrande.data.datasets.push(
                {
                    label: `Pronóstico ARIMA (${pron.modelo})`,
                    data: pad(pron.pronostico),
                    borderColor: '#00ccff',
                    borderDash: [6, 4],
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.2
                },
                {
                    label: 'Límite superior',
                    data: pad(pron.superior),
                    borderColor: 'rgba(0,204,255,0.25)',
                    borderDash: [2, 3],
                    borderWidth: 1,
                    pointRadius: 0,
                    tension: 0.2
                },
                {
                    label: 'Límite inferior',
                    data: pad(pron.inferior),
                    borderColor: 'rgba(0,204,255,0.25)',
                    borderDash: [2, 3],
                    borderWidth: 1,
                    pointRadius: 0,
                    tension: 0.2,
                    fill: '-1',
                    backgroundColor: 'rgba(0,204,255,0.06)'
                }
            );
            graficoGrande.update('none');
        }

        function statScore(s) {
            if (!s || !s.etiqueta) return 0;
            const signo = s.etiqueta === 'COMPRA' ? 1 : s.etiqueta === 'VENTA' ? -1 : 0;
            if (signo === 0) return 0;
            return clampNum(signo * Math.min(1, Math.abs(s.prediccion_pct || 0) / 0.5), -1, 1);
        }

        function actualizarVeredicto() {
            const rojo = document.getElementById('semaforoRojo');
            const amarillo = document.getElementById('semaforoAmarillo');
            const verde = document.getElementById('semaforoVerde');
            const texto = document.getElementById('senalTexto');
            const detalleEl = document.getElementById('senalDetalle');
            const fuentes = document.getElementById('senalFuentes');
            const nota = document.getElementById('senalNota');

            const n = senalNoticias;
            const e = senalEstadistica;

            if (fuentes && (n || e)) fuentes.style.display = 'flex';
            if (nota && (n || e)) nota.style.display = 'block';

            if (!n && !e) {
                if (texto) texto.innerHTML = ' ESPERANDO ANÁLISIS...';
                if (detalleEl) detalleEl.innerHTML = 'DeepSeek analizando el sentimiento del mercado';
                return;
            }

            let puntaje, fuenteInfo, reserva = false;
            if (n && e) {
                const sn = clampNum(n.score, -1, 1);
                const se = clampNum(e.score, -1, 1);
                puntaje = 0.6 * sn + 0.4 * se;
                const signoN = Math.sign(sn) || 0;
                const signoE = Math.sign(se) || 0;
                if (signoN !== 0 && signoE !== 0 && signoN !== signoE) reserva = true;
                fuenteInfo = `Combinacion: 60% noticias (${n.etiqueta}) + 40% estadistica (${e.etiqueta})`;
            } else if (n) {
                puntaje = n.score;
                fuenteInfo = `Usando solo noticias (${n.etiqueta}): el analisis estadistico aun no esta disponible`;
            } else {
                puntaje = e.score;
                fuenteInfo = `Usando solo estadistica (${e.etiqueta}): el analisis de noticias aun no esta disponible`;
            }

            let confianza = clampNum(0.5 + Math.abs(puntaje) * 0.8, 0, 1);
            if (reserva) confianza *= 0.6;

            let clase, etiqueta;
            if (puntaje >= 0.05) { clase = 'verde'; etiqueta = 'COMPRAR'; }
            else if (puntaje <= -0.05) { clase = 'rojo'; etiqueta = 'VENDER'; }
            else { clase = 'amarillo'; etiqueta = 'MANTENER'; }

            if (rojo && amarillo && verde) {
                [rojo, amarillo, verde].forEach(el => el.classList.remove('verde', 'amarillo', 'rojo'));
                document.getElementById('semaforo' + (clase === 'verde' ? 'Verde' : clase === 'rojo' ? 'Rojo' : 'Amarillo')).classList.add(clase);
            }
            if (texto) texto.innerHTML = ' SEÑAL: ' + etiqueta;
            if (detalleEl) detalleEl.innerHTML = fuenteInfo + (reserva ? ' (señal con reserva)' : '') + ` · confianza ${Math.round(confianza * 100)}%`;
        }

        function mostrarSenalEstadistica(s) {
            const badge = document.getElementById('badgeEstadistica');
            const sub = document.getElementById('subEstadistica');
            if (!badge) return;
            if (!s || !s.etiqueta) {
                senalEstadistica = null;
                badge.textContent = '—';
                badge.className = 'senal-fuente-badge';
                if (sub) sub.textContent = '';
                actualizarVeredicto();
                return;
            }
            senalEstadistica = {
                score: statScore(s),
                etiqueta: s.etiqueta,
                detalle: `prediccion ${fmtCompSigned(s.prediccion_pct || 0)}% diaria · confianza ${Math.round((s.confianza || 0) * 100)}%`
            };
            badge.textContent = s.etiqueta;
            badge.className = 'senal-fuente-badge ' + (s.etiqueta === 'COMPRA' ? 'compra' : s.etiqueta === 'VENTA' ? 'venta' : 'neutral');
            if (sub) sub.textContent = senalEstadistica.detalle;
            actualizarVeredicto();
        }

        async function cargarGraficoGrande() {
            try {
                const resp = await fetch(`${API_BASE}/api/historico_par/${monedaFrom}/${monedaTo}?dias=80`);
                const data = await resp.json();
                if (data.datos) dibujarGraficoGrande(data.datos);
                const respP = await fetch(`${API_BASE}/api/pronostico/${monedaFrom}/${monedaTo}?dias=80`);
                const dataP = await respP.json();
                if (dataP.success) {
                    ultimoPronostico = dataP;
                    aplicarPronostico(dataP);
                    mostrarSenalEstadistica(dataP.senal_estadistica);
                }
            } catch (e) {
                console.log('Error cargando gráfico grande:', e);
            }
        }

        function actualizarPrecioDisplay() {
            cargarPar();
        }
        
        // ========== SIMULACIÓN CON ESTRATEGIA SMA CROSSOVER ==========
        function calcularSMA(data, periodo) {
            const sma = [];
            for (let i = 0; i < data.length; i++) {
                if (i < periodo - 1) { sma.push(null); continue; }
                let sum = 0;
                for (let j = i - periodo + 1; j <= i; j++) sum += data[j];
                sma.push(sum / periodo);
            }
            return sma;
        }

        async function iniciarSimulacion() {
            if (simulacionActiva) return;
            resetearGuardado();
            
            if (monedaFrom === monedaTo) {
                mostrarNotificacion('Selecciona dos monedas diferentes para simular', 'error');
                return;
            }
            
            const montoInput = document.getElementById('montoInvertir').value;
            if (!montoInput || montoInput.trim() === '') {
                mostrarNotificacion('Ingresa un monto para invertir', 'error');
                return;
            }
            const monto = parseFloat(montoInput);
            if (isNaN(monto) || monto < 0) {
                mostrarNotificacion('El monto minimo es $0', 'error');
                return;
            }
            
            const btnIniciar = document.getElementById('btnIniciar');
            btnIniciar.disabled = true;
            btnIniciar.innerHTML = ' Cargando datos históricos...';
            
            try {
                const resp = await fetch(`${API_BASE}/api/historico_par/${monedaFrom}/${monedaTo}?dias=80`);
                const data = await resp.json();
                historicoData = data.datos || [];
            } catch (e) {
                console.log('Error cargando histórico:', e);
                mostrarNotificacion('Error al conectar con el servidor', 'error');
                btnIniciar.disabled = false;
                btnIniciar.innerHTML = ' Iniciar Simulación';
                return;
            }
            
            if (historicoData.length < 25) {
                mostrarNotificacion('No hay suficientes datos históricos disponibles', 'error');
                btnIniciar.disabled = false;
                btnIniciar.innerHTML = ' Iniciar Simulación';
                return;
            }
            
            let capital = monto;
            let acciones = 0;
            let historialCapital = [];
            maxCapitalSim = monto;
            diaActual = 0;
            simulacionActiva = true;
            
            const precios = historicoData.map(d => d.precio);
            
            btnIniciar.innerHTML = 'Simulando...';
            document.getElementById('simProgress').style.display = 'block';
            document.getElementById('smaDisplay').style.display = 'flex';
            document.getElementById('simEstadoTexto').textContent = 'Simulando...';
            
            intervaloSim = setInterval(() => {
                if (diaActual >= precios.length) {
                    finalizarSimulacion(precios, capital, acciones, historialCapital, monto);
                    return;
                }
                
                const precio = precios[diaActual];
                const sma5 = calcularSMA(precios.slice(0, diaActual + 1), 5);
                const sma20 = calcularSMA(precios.slice(0, diaActual + 1), 20);
                const s5 = sma5[sma5.length - 1];
                const s20 = sma20[sma20.length - 1];
                
                if (diaActual >= 20 && s5 !== null && s20 !== null) {
                    const prevS5 = sma5.length >= 2 ? sma5[sma5.length - 2] : null;
                    const prevS20 = sma20.length >= 2 ? sma20[sma20.length - 2] : null;
                    
                    if (prevS5 !== null && prevS20 !== null) {
                        if (prevS5 <= prevS20 && s5 > s20 && capital > 0) {
                            const fraccion = obtenerFraccionPosicion(monto);
                            acciones = (capital * fraccion) / precio;
                            capital = capital * (1 - fraccion);
                            historialSenales.push({ tipo: 'compra', dia: diaActual, precio: precio });
                        } else if (prevS5 >= prevS20 && s5 < s20 && acciones > 0) {
                            capital = acciones * precio;
                            acciones = 0;
                            historialSenales.push({ tipo: 'venta', dia: diaActual, precio: precio });
                        }
                    }
                }
                
                let capitalTotal = capital + (acciones * precio);

                if (acciones > 0) {
                    if (capitalTotal > maxCapitalSim) maxCapitalSim = capitalTotal;
                    if (capitalTotal < maxCapitalSim * (1 - obtenerStopLossPct(monto))) {
                        capital = acciones * precio;
                        acciones = 0;
                        capitalTotal = capital;
                        historialSenales.push({ tipo: 'stop-loss', dia: diaActual, precio: precio });
                        mostrarNotificacion('Stop-loss activado: posición vendida automáticamente', 'error');
                    }
                }

                historialCapital.push(capitalTotal);

                const infoFrom = SIMBOLOS_MONEDA[monedaFrom];
                const infoTo = SIMBOLOS_MONEDA[monedaTo];
                const rend = ((capitalTotal - monto) / monto * 100);

                document.getElementById('posicionTexto').textContent = acciones > 0 ? 'EN POSICIÓN' : 'SIN POSICIÓN';
                document.getElementById('posicionTexto').style.color = acciones > 0 ? '#00ff88' : '#ffaa00';
                document.getElementById('capitalTexto').textContent = `${infoTo.simbolo}${capitalTotal.toFixed(2)}`;
                document.getElementById('rendimientoTexto').textContent = `${rend >= 0 ? '+' : ''}${rend.toFixed(2)}%`;
                document.getElementById('rendimientoTexto').style.color = rend >= 0 ? '#00ff88' : '#ff4444';

                document.getElementById('diaActualTexto').textContent = `Dia ${diaActual + 1}/${precios.length}`;
                document.getElementById('simProgressFill').style.width = `${((diaActual + 1) / precios.length * 100).toFixed(0)}%`;

                if (s5 !== null && s20 !== null) {
                    document.getElementById('sma5Val').textContent = s5.toFixed(4);
                    document.getElementById('sma20Val').textContent = s20.toFixed(4);
                }

                dibujarGraficoGrande(precios, diaActual + 1);

                diaActual++;
            }, 100);
        }
        
        function finalizarSimulacion(precios, capital, acciones, historialCapital, montoInicial) {
            clearInterval(intervaloSim);
            simulacionActiva = false;
            
            const btnIniciar = document.getElementById('btnIniciar');
            btnIniciar.disabled = false;
            btnIniciar.innerHTML = ' Iniciar Simulación';
            
            if (precios.length === 0) return;
            
            const precioFinal = precios[precios.length - 1];
            const capitalFinal = capital + (acciones * precioFinal);
            const rendimiento = ((capitalFinal - montoInicial) / montoInicial * 100);

            const rendEl = document.getElementById('rendimientoVal');
            rendEl.textContent = `${rendimiento >= 0 ? '+' : ''}${rendimiento.toFixed(2)}%`;
            rendEl.className = 'big-number ' + (rendimiento >= 0 ? 'verde' : 'rojo');
            document.getElementById('capitalFinal').textContent = `${SIMBOLOS_MONEDA[monedaTo].simbolo}${capitalFinal.toFixed(2)}`;

            const rendBar = document.getElementById('rendimientoBar');
            const rendPct = Math.min(Math.max((rendimiento + 100) / 200 * 100, 0), 100);
            rendBar.style.width = rendPct + '%';
            rendBar.className = 'metric-bar-fill ' + (rendimiento >= 0 ? 'verde' : 'rojo');

            const returns = [];
            for (let i = 1; i < historialCapital.length; i++) {
                returns.push((historialCapital[i] - historialCapital[i-1]) / historialCapital[i-1]);
            }
            const avgRet = returns.reduce((a, b) => a + b, 0) / returns.length;
            const stdRet = Math.sqrt(returns.reduce((sum, r) => sum + (r - avgRet) ** 2, 0) / returns.length);
            const sharpe = stdRet > 0 ? (avgRet / stdRet) * Math.sqrt(252) : 0;
            const sharpeEl = document.getElementById('sharpeVal');
            sharpeEl.textContent = sharpe.toFixed(2);
            sharpeEl.className = 'big-number ' + (sharpe >= 1 ? 'verde' : sharpe >= 0 ? 'amarillo' : 'rojo');

            const sharpeBar = document.getElementById('sharpeBar');
            const sharpePct = Math.min(Math.max((sharpe + 2) / 4 * 100, 0), 100);
            sharpeBar.style.width = sharpePct + '%';
            sharpeBar.className = 'metric-bar-fill ' + (sharpe >= 1 ? 'verde' : sharpe >= 0 ? 'amarillo' : 'rojo');

            const maxDrawdown = calcularMaxDrawdown(historialCapital);
            const ddEl = document.getElementById('drawdownVal');
            ddEl.textContent = `-${(maxDrawdown * 100).toFixed(1)}%`;
            ddEl.className = 'big-number ' + (maxDrawdown < 0.1 ? 'verde' : maxDrawdown < 0.25 ? 'amarillo' : 'rojo');

            const ddBar = document.getElementById('drawdownBar');
            ddBar.style.width = Math.min(maxDrawdown * 100, 100) + '%';
            ddBar.className = 'metric-bar-fill ' + (maxDrawdown < 0.1 ? 'verde' : maxDrawdown < 0.25 ? 'amarillo' : 'rojo');

            const winRate = returns.filter(r => r > 0).length / returns.length * 100;
            const wrEl = document.getElementById('winRateVal');
            wrEl.textContent = `${winRate.toFixed(0)}%`;
            wrEl.className = 'big-number ' + (winRate >= 60 ? 'verde' : winRate >= 40 ? 'amarillo' : 'rojo');

            const wrBar = document.getElementById('winRateBar');
            wrBar.style.width = Math.min(winRate, 100) + '%';
            wrBar.className = 'metric-bar-fill ' + (winRate >= 60 ? 'verde' : winRate >= 40 ? 'amarillo' : 'rojo');
            
            document.getElementById('simEstadoTexto').textContent = 'Completado';
            document.getElementById('simProgressFill').style.width = '100%';

            const infoTo = SIMBOLOS_MONEDA[monedaTo];
            document.getElementById('posicionTexto').textContent = acciones > 0 ? 'EN POSICIÓN' : 'SIN POSICIÓN';
            document.getElementById('posicionTexto').style.color = acciones > 0 ? '#00ff88' : '#ffaa00';
            document.getElementById('capitalTexto').textContent = `${infoTo.simbolo}${capitalFinal.toFixed(2)}`;
            document.getElementById('rendimientoTexto').textContent = `${rendimiento >= 0 ? '+' : ''}${rendimiento.toFixed(2)}%`;
            document.getElementById('rendimientoTexto').style.color = rendimiento >= 0 ? '#00ff88' : '#ff4444';

            const generado = capitalFinal - montoInicial;
            const generadoEl = document.getElementById('generadoDisplay');
            const generadoTexto = document.getElementById('generadoTexto');
            generadoEl.style.display = 'block';
            generadoTexto.textContent = `${generado >= 0 ? '+' : '-'}${infoTo.simbolo}${Math.abs(generado).toFixed(2)}`;
            generadoTexto.style.color = generado >= 0 ? '#00ff88' : '#ff4444';

            registrarSimulacionActual({
                moneda: `${monedaFrom}/${monedaTo}`,
                monto: montoInicial,
                capital_inicial: montoInicial,
                capital_final: capitalFinal,
                rendimiento: rendimiento,
                generado: generado,
                sharpe: sharpe,
                drawdown: Math.max(maxDrawdown * 100, 0),
                win_rate: winRate,
                recomendacion: 'EN ANÁLISIS',
            });

            setTimeout(() => actualizarAnalisis(precios, rendimiento, sharpe, maxDrawdown * 100, winRate, montoInicial, capitalFinal), 500);
        }
        
        function obtenerFraccionPosicion(monto) {
            if (monto >= 50000) return 0.15;
            if (monto >= 10000) return 0.30;
            if (monto >= 1000) return 0.60;
            return 1.0;
        }

        function obtenerStopLossPct(monto) {
            if (monto >= 10000) return 0.05;
            if (monto >= 1000) return 0.10;
            return 0.15;
        }

        function calcularMaxDrawdown(precios) {
            let maxPrecio = precios[0];
            let maxDrawdown = 0;
            for (const p of precios) {
                if (p > maxPrecio) maxPrecio = p;
                const drawdown = (maxPrecio - p) / maxPrecio;
                if (drawdown > maxDrawdown) maxDrawdown = drawdown;
            }
            return maxDrawdown;
        }
        
        function pausarSimulacion() {
            clearInterval(intervaloSim);
            simulacionActiva = false;
            document.getElementById('btnIniciar').disabled = false;
            document.getElementById('btnIniciar').innerHTML = 'Iniciar Simulacion';
            document.getElementById('simEstadoTexto').textContent = 'Pausado';
        }
        
        function reiniciarSimulacion() {
            clearInterval(intervaloSim);
            simulacionActiva = false;
            historialSenales = [];
            maxCapitalSim = 0;
            document.getElementById('btnIniciar').disabled = false;
            document.getElementById('btnIniciar').innerHTML = ' Iniciar Simulación';
            actualizarPrecioDisplay();
            const resetEls = (id, val, cls) => {
                const el = document.getElementById(id);
                if (el) { el.textContent = val; el.className = 'big-number ' + cls; }
            };
            resetEls('rendimientoVal', '+0.0%', '');
            resetEls('sharpeVal', '0.00', '');
            resetEls('drawdownVal', '0.0%', '');
            resetEls('winRateVal', '0%', '');
            document.getElementById('capitalFinal').textContent = '$10,000.00';
            ['rendimientoBar', 'sharpeBar', 'drawdownBar', 'winRateBar'].forEach(id => {
                const el = document.getElementById(id);
                if (el) { el.style.width = '0%'; el.className = 'metric-bar-fill'; }
            });
            resetearSemaforo();
            document.getElementById('deepseekResult').innerHTML = '<p>Inicia la simulacion para obtener analisis</p>';
            document.getElementById('analisisExtra').style.display = 'none';
            document.getElementById('opcionesSection').style.display = 'none';
            document.getElementById('opcionesGrid').innerHTML = '';
            document.getElementById('opcionesAccionesGrid').innerHTML = '';
            document.getElementById('simProgress').style.display = 'none';
            document.getElementById('smaDisplay').style.display = 'none';
            document.getElementById('posicionTexto').textContent = '--';
            document.getElementById('posicionTexto').style.color = '';
            document.getElementById('capitalTexto').textContent = '--';
            document.getElementById('rendimientoTexto').textContent = '--';
            document.getElementById('rendimientoTexto').style.color = '';
            document.getElementById('generadoDisplay').style.display = 'none';
            document.getElementById('generadoTexto').textContent = '--';
            document.getElementById('montoInvertir').value = '';
        }

        // ========== SEMÁFORO ==========
        function actualizarSemaforo(sentimiento, detalle) {
            const badge = document.getElementById('badgeNoticias');
            const sub = document.getElementById('subNoticias');
            const etiqueta = sentimiento >= 0.05 ? 'COMPRAR' : sentimiento <= -0.05 ? 'VENDER' : 'MANTENER';
            senalNoticias = {
                score: clampNum(sentimiento, -1, 1),
                etiqueta: etiqueta,
                detalle: detalle || ''
            };
            if (badge) { badge.textContent = etiqueta; badge.className = 'senal-fuente-badge ' + (etiqueta === 'COMPRAR' ? 'compra' : etiqueta === 'VENDER' ? 'venta' : 'neutral'); }
            if (sub) sub.textContent = senalNoticias.detalle;
            actualizarVeredicto();
        }
        
        function resetearSemaforo() {
            senalNoticias = null;
            const badgeN = document.getElementById('badgeNoticias');
            if (badgeN) { badgeN.textContent = '—'; badgeN.className = 'senal-fuente-badge'; }
            const subN = document.getElementById('subNoticias');
            if (subN) subN.textContent = '';
            actualizarVeredicto();
        }
        
        // ========== ANÁLISIS IA (VADER + DeepSeek) ==========
        async function actualizarAnalisis(preciosHist, rendimiento, sharpe, drawdown, winRate, capitalInicial, capitalFinal) {
            let vaderData = null;
            try {
                const vaderResp = await fetch(`${API_BASE}/api/vader?query=forex+OR+trading+OR+divisas+OR+${monedaFrom}+OR+${monedaTo}&cantidad=2000`);
                vaderData = await vaderResp.json();
                if (!vaderData.error && vaderData.compound_score !== undefined) {
                    const vaderLabel = vaderData.clasificacion === 'alta' ? 'ALTA' : vaderData.clasificacion === 'baja' ? 'BAJA' : 'NEUTRAL';
                    const vaderDisplay = Math.abs(vaderData.compound_score) > 0.7 ? `MUY ${vaderLabel}` : vaderLabel;
                    actualizarSemaforo(vaderData.compound_score, `VADER: ${vaderDisplay} — basado en ${vaderData.noticias_analizadas} fuentes`);

                    document.getElementById('vaderScoreDisplay').textContent = vaderData.compound_score.toFixed(4);
                    document.getElementById('vaderScoreDisplay').style.color = vaderData.compound_score >= 0.05 ? '#00ff88' : vaderData.compound_score <= -0.05 ? '#ff4444' : '#ffaa00';
                    document.getElementById('totalFuentesDisplay').textContent = (vaderData.total_newsapi || 0) + (vaderData.total_google || 0) + (vaderData.total_gnews || 0);

                    const noticiasEl = document.getElementById('newsList');
                    const noticiasSection = document.getElementById('noticiasUsadas');
                    noticiasEl.innerHTML = '';
                    if (vaderData.noticias && vaderData.noticias.length > 0) {
                        vaderData.noticias.forEach(n => {
                            const li = document.createElement('li');
                            const badge = document.createElement('span');
                            badge.className = 'news-source ' + (n.fuente === 'DOF' ? 'dof' : 'newsapi');
                            badge.textContent = n.fuente === 'DOF' ? 'DOF' : n.fuente.substring(0, 8);
                            const title = document.createElement('a');
                            title.className = 'news-title';
                            title.textContent = n.titulo;
                            title.href = n.url || '#';
                            title.target = '_blank';
                            title.rel = 'noopener';
                            li.appendChild(badge);
                            li.appendChild(title);
                            noticiasEl.appendChild(li);
                        });
                        noticiasSection.style.display = 'block';
                    } else {
                        noticiasSection.style.display = 'none';
                    }

                    const yahooSymbol = monedaFrom + monedaTo + '=X';
                    const yahooUrl = 'https://finance.yahoo.com/quote/' + yahooSymbol;
                    const dofUrl = 'https://www.dof.gob.mx/index.php';
                    const fuentesLinks = document.getElementById('fuenteLinks');
                    fuentesLinks.innerHTML = '';
                    const links = [
                        { label: 'Yahoo Finance', url: yahooUrl, clase: 'yahoo' },
                        { label: 'DOF México', url: dofUrl, clase: 'dof-link' },
                    ];
                    links.forEach(l => {
                        const a = document.createElement('a');
                        a.href = l.url;
                        a.target = '_blank';
                        a.rel = 'noopener';
                        a.className = 'fuente-link ' + l.clase;
                        a.textContent = l.label;
                        fuentesLinks.appendChild(a);
                    });
                    document.getElementById('fuentesExternas').style.display = 'block';
                }
            } catch (e) {
                console.log('Error obteniendo análisis VADER:', e);
            }

            try {
                const precios = preciosHist || historicoData;
                const resp = await fetch(`${API_BASE}/api/analizar_historico`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        moneda: `${monedaFrom}/${monedaTo}`,
                        precios: precios.map((p, i) => typeof p === 'number' ? { fecha: `dia-${i+1}`, precio: p } : p),
                        capital_inicial: capitalInicial || 0,
                        capital_final: capitalFinal || 0,
                        rendimiento: rendimiento || 0,
                        sharpe: sharpe || 0,
                        drawdown: drawdown || 0,
                        win_rate: winRate || 0,
                        vader: vaderData && !vaderData.error ? {
                            compound_score: vaderData.compound_score,
                            clasificacion: vaderData.clasificacion,
                            noticias_analizadas: vaderData.noticias_analizadas,
                            noticias: vaderData.noticias || [],
                        } : null,
                    }),
                });
                const data = await resp.json();

                if (data.error || !data.analisis) {
                    throw new Error(data.error || 'Análisis no disponible');
                }

                const ai = data.analisis;
                const valorSentimiento = ai.valor || 0;
                const sentimientoLabel = ai.sentimiento === 'alta' ? 'ALTA' : ai.sentimiento === 'baja' ? 'BAJA' : 'NEUTRAL';
                const sentimientoDisplay = Math.abs(valorSentimiento) > 0.7 ? `MUY ${sentimientoLabel}` : sentimientoLabel;

                actualizarSemaforo(valorSentimiento, `DeepSeek: ${sentimientoDisplay} -- ${ai.analisis?.substring(0, 100)}...`);

                let resumenSimple = '';
                if (capitalInicial > 0) {
                    const recSimp = (ai.recomendacion || 'MANTENER');
                    const sentRec = recSimp === 'COMPRAR' ? 'ahora conviene <strong>comprar</strong>' : recSimp === 'VENDER' ? 'ahora conviene <strong>vender o esperar</strong>' : 'por ahora lo mejor es <strong>mantenerte como estás</strong>';
                    const confSimp = Math.min(Math.max((ai.confianza || 0) * 100, 0), 100);
                    resumenSimple = '<p class="ai-simple"><strong>En palabras simples:</strong><br>'
                        + `Empezaste con <strong>$${fmtComp(capitalInicial)}</strong> y terminaste con <strong>$${fmtComp(capitalFinal)}</strong>, un rendimiento de <strong>${fmtCompSigned(rendimiento || 0)}%</strong>. `
                        + `De cada 100 operaciones, <strong>${fmtComp(winRate || 0)}%</strong> salieron ganando, y lo peor que llegó a caer tu dinero fue <strong>-${fmtComp(Math.abs(drawdown || 0))}%</strong>. `
                        + `Con esa información, el sistema dice que ${sentRec}, con una confianza del ${confSimp.toFixed(0)}%.</p>`;
                }

                let pronIAHtml = '';
                if (data.pronostico && data.pronostico.modelo) {
                    const pR = data.pronostico;
                    const ult = pR.pronostico.length - 1;
                    pronIAHtml = `<p class="ai-simple"><strong>Pronóstico estadístico (${pR.modelo}):</strong> ${fmtCompSigned(pR.cambio_pct || 0)}% en 5 días · rango $${fmtComp(pR.inferior[ult])} a $${fmtComp(pR.superior[ult])}`;
                    const sE = data.senal_estadistica;
                    if (sE && sE.etiqueta) {
                        pronIAHtml += ` · señal ARMA: ${sE.etiqueta} (${Math.round((sE.confianza || 0) * 100)}%)`;
                    }
                    pronIAHtml += '</p>';
                }

                document.getElementById('deepseekResult').innerHTML = `
                    <p><strong>DeepSeek -- Veredicto Final</strong></p>
                    ${resumenSimple}
                    ${pronIAHtml}
                    <p>${ai.analisis}</p>
                    <p><small>Basado en Yahoo Finance + VADER (noticias) + DeepSeek + ARIMA/ARMA</small></p>
                `;

                const badge = document.getElementById('sentimentBadge');
                badge.textContent = sentimientoDisplay;
                badge.className = 'sentiment-badge ' + (ai.sentimiento || 'neutral');

                const confianza = Math.min(Math.max((ai.confianza || 0) * 100, 0), 100);
                document.getElementById('confianzaTexto').textContent = confianza.toFixed(0) + '%';
                const bar = document.getElementById('confianzaBar');
                bar.style.width = confianza + '%';
                bar.className = 'confidence-bar-fill ' + (ai.sentimiento || 'neutral');

                const recTexto = document.getElementById('recomendacionTexto');
                const rec = ai.recomendacion || 'MANTENER';
                recTexto.textContent = rec;
                recTexto.style.color = rec === 'COMPRAR' ? '#00ff88' : rec === 'VENDER' ? '#ff4444' : '#ffaa00';

                document.getElementById('analisisExtra').style.display = 'block';

                const opciones = ai.opciones || [];
                const opcionesSection = document.getElementById('opcionesSection');
                const opcionesGrid = document.getElementById('opcionesGrid');
                const opcionesAccionesGrid = document.getElementById('opcionesAccionesGrid');
                const renderOpciones = (lista, contenedor) => {
                    contenedor.innerHTML = '';
                    if (lista.length === 0) return;
                    lista.forEach(op => {
                        const card = document.createElement('div');
                        const riesgo = ['bajo', 'medio', 'alto'].includes(op.riesgo) ? op.riesgo : 'medio';
                        card.className = 'opcion-card riesgo-' + riesgo;
                        const header = document.createElement('div');
                        header.className = 'opcion-header';
                        const titulo = document.createElement('span');
                        titulo.className = 'opcion-titulo';
                        titulo.textContent = op.titulo || 'Opcion';
                        const badge = document.createElement('span');
                        badge.className = 'opcion-riesgo';
                        badge.textContent = riesgo.toUpperCase();
                        header.appendChild(titulo);
                        header.appendChild(badge);
                        const accion = document.createElement('div');
                        accion.className = 'opcion-accion';
                        accion.textContent = op.accion || '';
                        const meta = document.createElement('div');
                        meta.className = 'opcion-meta';
                        if (op.ticker) {
                            const tickerSpan = document.createElement('span');
                            tickerSpan.className = 'opcion-ticker';
                            tickerSpan.textContent = op.ticker;
                            meta.appendChild(tickerSpan);
                            if (op.precio_actual) {
                                const precioSpan = document.createElement('span');
                                precioSpan.textContent = 'Precio: $' + op.precio_actual;
                                meta.appendChild(precioSpan);
                            }
                        }
                        if (op.par) {
                            const parSpan = document.createElement('span');
                            parSpan.textContent = 'Par: ' + op.par;
                            meta.appendChild(parSpan);
                        }
                        const retornoSpan = document.createElement('span');
                        retornoSpan.textContent = 'Retorno esperado: ' + (op.retorno_esperado || '—');
                        meta.appendChild(retornoSpan);
                        const razon = document.createElement('p');
                        razon.className = 'opcion-razon';
                        razon.textContent = op.razon || '';
                        card.appendChild(header);
                        card.appendChild(accion);
                        card.appendChild(meta);
                        card.appendChild(razon);
                        contenedor.appendChild(card);
                    });
                };
                renderOpciones(opciones, opcionesGrid);
                renderOpciones((ai.opciones_acciones || []).slice(0, 5), opcionesAccionesGrid);
                if (opciones.length > 0 || (ai.opciones_acciones || []).length > 0) {
                    opcionesSection.style.display = 'block';
                } else {
                    opcionesSection.style.display = 'none';
                }

                const simDatos = {
                    moneda: simActualDatos && simActualDatos.moneda ? simActualDatos.moneda : `${monedaFrom}/${monedaTo}`,
                    monto: capitalInicial || (simActualDatos && simActualDatos.monto) || 0,
                    capital_inicial: capitalInicial || (simActualDatos && simActualDatos.capital_inicial) || 0,
                    capital_final: capitalFinal || (simActualDatos && simActualDatos.capital_final) || 0,
                    rendimiento: rendimiento || (simActualDatos && simActualDatos.rendimiento) || 0,
                    sharpe: sharpe || (simActualDatos && simActualDatos.sharpe) || 0,
                    drawdown: drawdown || (simActualDatos && simActualDatos.drawdown) || 0,
                    win_rate: winRate || (simActualDatos && simActualDatos.win_rate) || 0,
                    generado: (capitalFinal || (simActualDatos && simActualDatos.capital_final) || 0) - (capitalInicial || (simActualDatos && simActualDatos.capital_inicial) || 0),
                    compound: (vaderData && !vaderData.error ? vaderData.compound_score : 0) || 0,
                    sentimiento: ai.sentimiento || 'neutral',
                    recomendacion: ai.recomendacion || 'MANTENER',
                    confianza: ai.confianza || 0,
                    analisis: ai.analisis || '',
                };
                guardarSimulacion(simDatos);
                registrarSimulacionActual(simDatos);
            } catch (e) {
                console.log('Error en análisis DeepSeek:', e);
                if (!vaderData || vaderData.error) {
                    document.getElementById('deepseekResult').innerHTML = `
                        <div class="deepseek-card">
                            <p><strong> Análisis no disponible</strong></p>
                            <p><small> No se pudo obtener análisis de DeepSeek ni VADER</small></p>
                        </div>
                    `;
                } else {
                    const clasif = vaderData.clasificacion;
                    const label = clasif === 'alta' ? 'ALTA' : clasif === 'baja' ? 'BAJA' : 'NEUTRAL';
                    const displayLabel = Math.abs(vaderData.compound_score) > 0.7 ? `MUY ${label}` : label;
                    document.getElementById('deepseekResult').innerHTML = `
                        <div class="deepseek-card">
                            <p><strong> Análisis VADER (DeepSeek no disponible)</strong></p>
                            <p><strong>Sentimiento:</strong> ${displayLabel} (compound: ${vaderData.compound_score})</p>
                            <p><strong>Noticias analizadas:</strong> ${vaderData.noticias_analizadas}</p>
                            <p><small> Basado en noticias financieras vía VADER</small></p>
                        </div>
                    `;
                }
            }
        }
        
        async function verificarBackend() {
            const estadoSpan = document.getElementById('estadoBackend');
            if (!estadoSpan) return;
            try {
                const resp = await fetch(`${API_BASE}/api/test`);
                if (resp.ok) {
                    const preciosResp = await fetch(`${API_BASE}/api/precios`);
                    const preciosData = await preciosResp.json();
                    if (preciosData.monedas) {
                        for (const [moneda, info] of Object.entries(preciosData.monedas)) {
                            preciosActuales[moneda] = info.precio;
                        }
                        cargarPar();
                    }
                    estadoSpan.innerHTML = ' Conectado (yfinance)';
                    estadoSpan.style.color = '#4cff4c';
                } else {
                    throw new Error('Error');
                }
            } catch (e) {
                estadoSpan.innerHTML = ' No conectado';
                estadoSpan.style.color = '#ffaa00';
            }
        }
        
        function mostrarNotificacion(mensaje, tipo = 'success') {
            const notif = document.createElement('div');
            notif.textContent = mensaje;
            notif.style.cssText = `
                position: fixed; bottom: 20px; right: 20px; padding: 12px 20px;
                background: ${tipo === 'success' ? '#10b981' : '#3b82f6'};
                color: white; border-radius: 8px; z-index: 10000;
                animation: fadeIn 0.3s, fadeOut 0.3s 2.7s forwards;
            `;
            document.body.appendChild(notif);
            setTimeout(() => notif.remove(), 3000);
        }
    
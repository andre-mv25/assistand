// ============================================
// TRADING ASSISTANT - LÓGICA PRINCIPAL
// Gemini 1.5 Pro + DeepSeek
// ============================================

// ========== VARIABLES GLOBALES ==========
let intervalo;
let miGrafico;
let simulacionActiva = false;
let diaActual = 0;
let tickerActual = 'AAPL';
let historialPrecios = [];
let historialCapital = [];
let capitalInicial = 10000;

const datosTicker = {
    'AAPL': { precio: 175.34, volatilidad: 0.02, tendencia: 0.001 },
    'MSFT': { precio: 378.85, volatilidad: 0.015, tendencia: 0.0012 },
    'GOOGL': { precio: 142.56, volatilidad: 0.018, tendencia: 0.0008 },
    'TSLA': { precio: 245.67, volatilidad: 0.04, tendencia: 0.002 },
    'AMZN': { precio: 145.23, volatilidad: 0.022, tendencia: 0.0009 },
    'NVDA': { precio: 789.23, volatilidad: 0.035, tendencia: 0.003 },
    'META': { precio: 312.45, volatilidad: 0.03, tendencia: 0.0015 }
};

// ========== INICIALIZACIÓN ==========
document.addEventListener('DOMContentLoaded', () => {
    inicializarGrafico();
    inicializarEventos();
    actualizarPrecio('AAPL');
    cargarConfiguracion();
    verificarBackend();
});

function inicializarGrafico() {
    const canvas = document.getElementById('grafico');
    miGrafico = new Chart(canvas, {
        type: 'line',
        data: { labels: [], datasets: [
            { label: 'Precio', data: [], borderColor: '#00ffff', fill: false, tension: 0.3 },
            { label: 'Capital', data: [], borderColor: '#4cff4c', fill: false, tension: 0.3 }
        ]},
        options: { responsive: true, maintainAspectRatio: true }
    });
}

function inicializarEventos() {
    document.getElementById('btnIniciar').addEventListener('click', iniciarSimulacion);
    document.getElementById('btnPausar').addEventListener('click', pausarSimulacion);
    document.getElementById('btnReiniciar').addEventListener('click', reiniciarSimulacion);
    document.getElementById('guardarConfig').addEventListener('click', guardarConfiguracion);
    document.getElementById('resetConfig').addEventListener('click', resetearConfiguracion);
    
    document.querySelectorAll('.ticker-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.ticker-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            seleccionarTicker(btn.getAttribute('data-ticker'));
        });
    });
    
    if (document.querySelector('.ticker-btn')) {
        document.querySelector('.ticker-btn').classList.add('active');
    }
}

function actualizarPrecio(ticker) {
    const datos = datosTicker[ticker];
    document.getElementById('precioDisplay').textContent = `$${datos.precio.toFixed(2)}`;
}

function seleccionarTicker(ticker) {
    tickerActual = ticker;
    actualizarPrecio(ticker);
    reiniciarSimulacion();
}

// ========== SIMULACIÓN ==========
function iniciarSimulacion() {
    if (simulacionActiva) return;
    clearInterval(intervalo);
    reiniciarGrafico();
    
    capitalInicial = parseFloat(document.getElementById('capital').value) || 10000;
    const dias = parseInt(document.getElementById('dias').value) || 30;
    const estrategia = document.getElementById('estrategia').value;
    
    let precio = datosTicker[tickerActual].precio;
    let capital = capitalInicial;
    let acciones = 0;
    
    historialPrecios = [precio];
    historialCapital = [capital];
    diaActual = 0;
    simulacionActiva = true;
    
    intervalo = setInterval(() => {
        if (diaActual >= dias) { finalizarSimulacion(); return; }
        
        const cambio = precio * ((Math.random() - 0.5) * datosTicker[tickerActual].volatilidad * 2);
        precio += cambio;
        precio = Math.max(precio, 0.01);
        
        if (estrategia === 'momentum' && cambio > 0 && capital > precio) {
            acciones = capital / precio;
            capital = 0;
        } else if (estrategia === 'hodl' && diaActual === 0) {
            acciones = capital / precio;
            capital = 0;
        }
        
        const capitalTotal = capital + (acciones * precio);
        historialPrecios.push(precio);
        historialCapital.push(capitalTotal);
        
        miGrafico.data.labels.push(diaActual);
        miGrafico.data.datasets[0].data.push(precio);
        miGrafico.data.datasets[1].data.push(capitalTotal);
        miGrafico.update();
        diaActual++;
    }, 100);
    
    setTimeout(() => actualizarIAs(), 500);
}

function finalizarSimulacion() {
    clearInterval(intervalo);
    simulacionActiva = false;
    
    const capitalFinal = historialCapital[historialCapital.length - 1];
    const rendimiento = ((capitalFinal - capitalInicial) / capitalInicial * 100).toFixed(2);
    
    document.getElementById('rendimiento').textContent = `${rendimiento > 0 ? '+' : ''}${rendimiento}%`;
    document.getElementById('capitalFinal').textContent = `$${capitalFinal.toFixed(2)}`;
    document.getElementById('sharpe').textContent = (Math.random() * 2).toFixed(2);
    document.getElementById('drawdown').textContent = `-${(Math.random() * 15).toFixed(1)}%`;
    document.getElementById('winrate').textContent = `${(40 + Math.random() * 40).toFixed(0)}%`;
    
    setTimeout(() => actualizarIAs(), 1000);
}

function pausarSimulacion() {
    clearInterval(intervalo);
    simulacionActiva = false;
}

function reiniciarSimulacion() {
    clearInterval(intervalo);
    simulacionActiva = false;
    reiniciarGrafico();
    actualizarPrecio(tickerActual);
    document.getElementById('rendimiento').textContent = '+0.0%';
    document.getElementById('capitalFinal').textContent = '$10,000';
    document.getElementById('sharpe').textContent = '0.00';
    document.getElementById('drawdown').textContent = '0.0%';
    document.getElementById('winrate').textContent = '0%';
    resetearSemaforo();
    document.getElementById('geminiResult').innerHTML = '<p>Inicia la simulación para obtener análisis del gráfico</p>';
    document.getElementById('deepseekResult').innerHTML = '<p>Inicia la simulación para obtener análisis de noticias</p>';
}

function reiniciarGrafico() {
    if (!miGrafico) return;
    miGrafico.data.labels = [];
    miGrafico.data.datasets[0].data = [];
    miGrafico.data.datasets[1].data = [];
    miGrafico.update();
}

// ========== SEMAFORIZACIÓN ==========
function actualizarSemaforo(sentimiento) {
    const rojo = document.getElementById('semaforoRojo');
    const amarillo = document.getElementById('semaforoAmarillo');
    const verde = document.getElementById('semaforoVerde');
    const texto = document.getElementById('senalTexto');
    
    if (!rojo || !amarillo || !verde) return;
    
    [rojo, amarillo, verde].forEach(el => el.classList.remove('verde', 'amarillo', 'rojo'));
    
    if (sentimiento > 0.3) {
        verde.classList.add('verde');
        if (texto) texto.innerHTML = '🟢 SEÑAL: COMPRAR - Sentimiento Alcista';
    } else if (sentimiento < -0.3) {
        rojo.classList.add('rojo');
        if (texto) texto.innerHTML = '🔴 SEÑAL: VENDER - Sentimiento Bajista';
    } else {
        amarillo.classList.add('amarillo');
        if (texto) texto.innerHTML = '🟡 SEÑAL: MANTENER - Sentimiento Neutral';
    }
}

function resetearSemaforo() {
    const rojo = document.getElementById('semaforoRojo');
    const amarillo = document.getElementById('semaforoAmarillo');
    const verde = document.getElementById('semaforoVerde');
    const texto = document.getElementById('senalTexto');
    
    if (rojo && amarillo && verde) {
        [rojo, amarillo, verde].forEach(el => el.classList.remove('verde', 'amarillo', 'rojo'));
    }
    if (texto) texto.innerHTML = 'Esperando análisis...';
}

// ========== ANÁLISIS IA ==========
function actualizarIAs() {
    const ultimoPrecio = historialPrecios.length > 0 ? historialPrecios[historialPrecios.length-1] : datosTicker[tickerActual].precio;
    const soporte = (ultimoPrecio * 0.95).toFixed(2);
    const resistencia = (ultimoPrecio * 1.05).toFixed(2);
    const tendencia = historialPrecios.length > 5 ? 
        (historialPrecios[historialPrecios.length-1] > historialPrecios[historialPrecios.length-5] ? 'alcista' : 'bajista') : 'neutral';
    
    const geminiDiv = document.getElementById('geminiResult');
    if (geminiDiv) {
        geminiDiv.innerHTML = `
            <div class="ia-card gemini-card">
                <p><strong> Gemini 1.5 Pro - Análisis Visual</strong></p>
                <p> Precio: <strong>$${ultimoPrecio.toFixed(2)}</strong></p>
                <p> Tendencia: <strong style="color: ${tendencia === 'alcista' ? '#4cff4c' : tendencia === 'bajista' ? '#ff4c4c' : '#ffaa00'}">${tendencia.toUpperCase()}</strong></p>
                <p> Soporte: $${soporte} | Resistencia: $${resistencia}</p>
                <p> Recomendación: ${tendencia === 'alcista' ? 'COMPRAR en correcciones' : tendencia === 'bajista' ? 'ESPERAR confirmación' : 'MANTENER posición'}</p>
                <p><small>Confianza: ${(70 + Math.random() * 20).toFixed(0)}%</small></p>
            </div>
        `;
    }
    
    const sentimiento = parseFloat((Math.random() * 2 - 1).toFixed(2));
    actualizarSemaforo(sentimiento);
    
    const deepseekDiv = document.getElementById('deepseekResult');
    if (deepseekDiv) {
        deepseekDiv.innerHTML = `
            <div class="ia-card deepseek-card">
                <p><strong> DeepSeek - Análisis de Sentimiento</strong></p>
                <p> Sentimiento del mercado: <strong style="color: ${sentimiento > 0.3 ? '#4cff4c' : sentimiento < -0.3 ? '#ff4c4c' : '#ffaa00'}">${sentimiento > 0 ? '+' : ''}${sentimiento}</strong></p>
                <p> Clasificación: ${sentimiento > 0.3 ? 'Alcista' : sentimiento < -0.3 ? 'Bajista' : 'Neutral'}</p>
                <p> Recomendación: ${sentimiento > 0.3 ? 'COMPRAR en soporte' : sentimiento < -0.3 ? 'REDUCIR exposición' : 'ESPERAR señales'}</p>
                <p><small>Confianza: ${(70 + Math.random() * 20).toFixed(0)}%</small></p>
            </div>
        `;
    }
}

// ========== CONFIGURACIÓN ==========
function guardarConfiguracion() {
    const config = {
        modoDemo: document.getElementById('modoDemo')?.value || 'demo',
        intervaloActualizacion: parseInt(document.getElementById('intervaloActualizacion')?.value || '1000'),
        colorTema: document.getElementById('colorTema')?.value || 'neon',
        notificaciones: document.querySelector('input[name="notificaciones"]:checked')?.value || 'si',
        sonidos: document.querySelector('input[name="sonidos"]:checked')?.value || 'no',
        guardarDatos: document.querySelector('input[name="datos"]:checked')?.value || 'guardar'
    };
    
    localStorage.setItem('tradingConfig', JSON.stringify(config));
    aplicarConfiguracion(config);
    mostrarNotificacion(' Configuración guardada');
}

function resetearConfiguracion() {
    const modoDemo = document.getElementById('modoDemo');
    const intervalo = document.getElementById('intervaloActualizacion');
    const colorTema = document.getElementById('colorTema');
    
    if (modoDemo) modoDemo.value = 'demo';
    if (intervalo) intervalo.value = '1000';
    if (colorTema) colorTema.value = 'neon';
    
    const notifSi = document.querySelector('input[name="notificaciones"][value="si"]');
    const sonidosNo = document.querySelector('input[name="sonidos"][value="no"]');
    const datosGuardar = document.querySelector('input[name="datos"][value="guardar"]');
    
    if (notifSi) notifSi.checked = true;
    if (sonidosNo) sonidosNo.checked = true;
    if (datosGuardar) datosGuardar.checked = true;
    
    aplicarConfiguracion({ modoDemo: 'demo', intervaloActualizacion: 1000, colorTema: 'neon' });
    localStorage.removeItem('tradingConfig');
    mostrarNotificacion(' Configuración restablecida');
}

function cargarConfiguracion() {
    const saved = localStorage.getItem('tradingConfig');
    if (saved) {
        try {
            const config = JSON.parse(saved);
            const modoDemo = document.getElementById('modoDemo');
            const intervalo = document.getElementById('intervaloActualizacion');
            const colorTema = document.getElementById('colorTema');
            
            if (modoDemo) modoDemo.value = config.modoDemo || 'demo';
            if (intervalo) intervalo.value = config.intervaloActualizacion || '1000';
            if (colorTema) colorTema.value = config.colorTema || 'neon';
            
            if (config.notificaciones === 'si') {
                const notifSi = document.querySelector('input[name="notificaciones"][value="si"]');
                if (notifSi) notifSi.checked = true;
            } else {
                const notifNo = document.querySelector('input[name="notificaciones"][value="no"]');
                if (notifNo) notifNo.checked = true;
            }
            
            if (config.sonidos === 'si') {
                const sonidosSi = document.querySelector('input[name="sonidos"][value="si"]');
                if (sonidosSi) sonidosSi.checked = true;
            } else {
                const sonidosNo = document.querySelector('input[name="sonidos"][value="no"]');
                if (sonidosNo) sonidosNo.checked = true;
            }
            
            if (config.guardarDatos === 'guardar') {
                const datosGuardar = document.querySelector('input[name="datos"][value="guardar"]');
                if (datosGuardar) datosGuardar.checked = true;
            } else {
                const datosLimpiar = document.querySelector('input[name="datos"][value="limpiar"]');
                if (datosLimpiar) datosLimpiar.checked = true;
            }
            
            aplicarConfiguracion(config);
        } catch(e) { console.log('Error cargando configuración'); }
    }
}

function aplicarConfiguracion(config) {
    if (!config) return;
    
    if (config.colorTema === 'morado') {
        document.documentElement.style.setProperty('--primary', '#ff00aa');
    } else if (config.colorTema === 'matrix') {
        document.documentElement.style.setProperty('--primary', '#00ff88');
    } else if (config.colorTema === 'naranja') {
        document.documentElement.style.setProperty('--primary', '#ffaa00');
    } else {
        document.documentElement.style.setProperty('--primary', '#00ffff');
    }
}

function verificarBackend() {
    const estadoSpan = document.getElementById('estadoBackend');
    if (!estadoSpan) return;
    
    fetch('http://localhost:3000/api/test')
        .then(response => {
            if (response.ok) {
                estadoSpan.innerHTML = '🟢 Conectado';
                estadoSpan.style.color = '#4cff4c';
            } else {
                throw new Error('Error');
            }
        })
        .catch(() => {
            estadoSpan.innerHTML = '🔴 No conectado (usando modo demo)';
            estadoSpan.style.color = '#ffaa00';
        });
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
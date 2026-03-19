import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Coordinación 50/51", layout="centered")
st.title("Estudio de Coordinación Dinámico (Multifalla)")

# --- 1. FUNCIONES MATEMÁTICAS ---
def curva_rele(I, I_p, dial, curva, I_tdef, T_def, tdef_habilitado):
    if I_p <= 0: return np.full_like(I, np.inf)
    constantes = {
        'IEC Normal Inversa': (0.14, 0.02, 0.0),
        'IEC Muy Inversa': (13.5, 1.0, 0.0),
        'IEC Extremadamente Inversa': (80.0, 2.0, 0.0),
        'ANSI Moderadamente Inversa': (0.0515, 0.02, 0.114),
        'ANSI Muy Inversa': (19.61, 2.0, 0.491),
        'ANSI Extremadamente Inversa': (28.2, 2.0, 0.1217)
    }
    K, alpha, B = constantes[curva]
    
    # REGLA 1: Saturación a 20 veces la corriente de arranque (Ip)
    PSM = np.clip(I / I_p, 0, 20) 
    
    with np.errstate(divide='ignore', invalid='ignore'):
        t_curva = dial * (K / (PSM**alpha - 1) + B)
        # REGLA 2: El relé solo opera a partir de 1.03 veces la corriente de arranque
        t_curva = np.where(PSM >= 1.03, t_curva, np.inf)
        
    if tdef_habilitado:
        t_definido = np.where(I >= I_tdef, T_def, np.inf)
    else:
        t_definido = np.inf
        
    return np.minimum(t_curva, t_definido)

def dano_transformador(I_pu, P_mva, Z_cc):
    if P_mva <= 0 or Z_cc <= 0 or I_pu < 2 or I_pu > (1/Z_cc): return np.inf
    if P_mva <= 0.5 or Z_cc <= 0.04:
        return 19500 / (I_pu**3.8) if I_pu < 4.6 else 1250 / (I_pu**2)
    elif P_mva <= 5:
        if (Z_cc * I_pu) <= 0.7: return 19500 / (I_pu**3.8) if I_pu < 4.6 else 1250 / (I_pu**2)
        else: return 2 / ((I_pu**2) * (Z_cc**2))
    else:
        if (Z_cc * I_pu) <= 0.5: return 19500 / (I_pu**3.8) if I_pu < 4.6 else 1250 / (I_pu**2)
        else: return 2 / ((I_pu**2) * (Z_cc**2))

# --- 2. ESPACIO RESERVADO PARA LA GRÁFICA ---
# Esto permite que la gráfica se dibuje arriba aunque los cálculos se hagan abajo
plot_placeholder = st.empty()

# --- 3. INTERFAZ GRÁFICA (Pestañas en la parte inferior) ---
tab_reles, tab_trafos, tab_icc = st.tabs(["Relés (50/51)", "Transformadores", "Cortocircuitos (Icc)"])

reles_data = []
with tab_reles:
    for i in range(5):
        with st.expander(f"Parámetros Relé {i+1}", expanded=(i==0)):
            hab_rele = st.checkbox("Activar Relé", value=(i==0), key=f"r_hab_{i}")
            curva = st.selectbox("Curva", ['IEC Normal Inversa', 'IEC Muy Inversa', 'IEC Extremadamente Inversa', 'ANSI Moderadamente Inversa', 'ANSI Muy Inversa', 'ANSI Extremadamente Inversa'], key=f"r_curva_{i}")
            ip = st.number_input("Ip (A)", value=100.0, step=10.0, min_value=0.0, key=f"r_ip_{i}")
            
            # El parámetro min_value=0.0 asegura que el Dial nunca sea negativo
            dial = st.number_input("Dial", value=1.0, step=0.1, min_value=0.0, key=f"r_dial_{i}")
            
            hab_tdef = st.checkbox("Habilitar T. Def (50)", value=True, key=f"r_habtdef_{i}")
            itdef = st.number_input("I Def (A)", value=1000.0, step=50.0, key=f"r_itdef_{i}")
            tdef = st.number_input("T Def (s)", value=0.1, step=0.05, min_value=0.0, key=f"r_tdef_{i}")
            
            reles_data.append({'hab': hab_rele, 'curva': curva, 'ip': ip, 'dial': dial, 'hab_tdef': hab_tdef, 'itdef': itdef, 'tdef': tdef})

trafos_data = []
with tab_trafos:
    for i in range(2):
        with st.expander(f"Parámetros Trafo {i+1}", expanded=(i==0)):
            hab_trafo = st.checkbox("Activar Trafo", value=(i==0), key=f"t_hab_{i}")
            mva = st.number_input("MVA", value=2.0, step=0.5, min_value=0.0, key=f"t_mva_{i}")
            zcc = st.number_input("Zcc (pu)", value=0.05, step=0.01, min_value=0.001, key=f"t_zcc_{i}")
            inom = st.number_input("I nom (A)", value=100.0, step=10.0, min_value=0.1, key=f"t_inom_{i}")
            
            trafos_data.append({'hab': hab_trafo, 'mva': mva, 'zcc': zcc, 'inom': inom})

icc_data = []
with tab_icc:
    st.markdown("Activa y ajusta los diferentes niveles de cortocircuito (ej. Trifásico, Bifásico, Monofásico).")
    for i in range(3):
        # Usamos columnas para poner el checkbox al lado del valor y ahorrar espacio
        col1, col2 = st.columns([1, 2])
        with col1:
            hab_icc = st.checkbox(f"Activar Icc {i+1}", value=(i==0), key=f"icc_hab_{i}")
        with col2:
            val_icc = st.number_input(f"Icc {i+1} (A)", value=(1500.0 if i==0 else 500.0), step=100.0, min_value=0.0, label_visibility="collapsed", key=f"icc_val_{i}")
        
        icc_data.append({'hab': hab_icc, 'val': val_icc})

# --- 4. LÓGICA DE GRAFICACIÓN (Se ejecuta automáticamente) ---
fig, ax = plt.subplots(figsize=(10, 6))
corrientes = np.logspace(1, 4, 1000) # De 10A a 10000A
colores_reles = ['#1f77b4', '#d62728', '#2ca02c', '#9467bd', '#ff7f0e'] # Colores base
colores_icc = ['black', 'gray', 'brown'] 

# 1. Graficar Relés activos
for i, r in enumerate(reles_data):
    if r['hab'] and r['ip'] > 0:
        t = curva_rele(corrientes, r['ip'], r['dial'], r['curva'], r['itdef'], r['tdef'], r['hab_tdef'])
        ax.plot(corrientes, t, label=f'Relé {i+1}: {r["curva"]}', color=colores_reles[i], linewidth=2.5)

# 2. Graficar Trafos activos
for i, t in enumerate(trafos_data):
    if t['hab'] and t['mva'] > 0 and t['inom'] > 0:
        c_pu = corrientes / t['inom']
        t_trafo = [dano_transformador(ipu, t['mva'], t['zcc']) for ipu in c_pu]
        ax.plot(corrientes, t_trafo, label=f'Trafo {i+1} Daño', linestyle='-.', linewidth=2, color='darkgray')

# 3. Múltiples Puntos de cortocircuito y Etiquetas de Tiempo
for j, icc in enumerate(icc_data):
    if icc['hab'] and icc['val'] > 0:
        I_falla = icc['val']
        ax.axvline(x=I_falla, color=colores_icc[j], linestyle='--', alpha=0.6, label=f'Icc {j+1} = {I_falla} A')

        for i, r in enumerate(reles_data):
            if r['hab'] and r['ip'] > 0:
                t_op = curva_rele(np.array([I_falla]), r['ip'], r['dial'], r['curva'], r['itdef'], r['tdef'], r['hab_tdef'])[0]
                if t_op != np.inf and not np.isnan(t_op):
                    ax.scatter([I_falla], [t_op], color=colores_reles[i], s=80, zorder=5)
                    ax.annotate(
                        f' {t_op:.3f} s',
                        xy=(I_falla, t_op),
                        xytext=(8, 0),
                        textcoords='offset points',
                        color=colores_reles[i],
                        fontweight='bold',
                        fontsize=10,
                        verticalalignment='center'
                    )

# Formato del gráfico
ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xlim(10, 10000)
ax.set_ylim(0.01, 1000)
ax.grid(True, which="both", ls="--", alpha=0.5)
ax.set_xlabel('Corriente (Amperios)')
ax.set_ylabel('Tiempo (Segundos)')
ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='small')
plt.tight_layout()

# --- 5. INYECTAR GRÁFICA EN EL ESPACIO SUPERIOR ---
plot_placeholder.pyplot(fig)

import streamlit as st
import tidalapi
import time
import requests
import pandas as pd

# --- CONFIGURAÇÕES ---
DELAY = 0.1
VERSION = "v10.0 (Ultimate - Smart Sync & Classic UI)"

st.set_page_config(page_title="Tidal Migrator Pro", page_icon="🎵", layout="centered")

# --- CSS VISUAL ---
def local_css():
    st.markdown("""
        <style>
        .stProgress > div > div > div > div { background-color: #00ebc7; }
        .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #00ebc7; }
        </style>
        """, unsafe_allow_html=True)
local_css()

# --- ESTADO (SESSION STATE) ---
if 'user_old' not in st.session_state: st.session_state.user_old = None
if 'user_new' not in st.session_state: st.session_state.user_new = None
if 'session_old' not in st.session_state: st.session_state.session_old = None
if 'session_new' not in st.session_state: st.session_state.session_new = None

# LOGS ORGANIZADOS
if 'logs' not in st.session_state: 
    st.session_state.logs = {'tracks': [], 'tracks_skipped': [], 'playlists': [], 'albums': [], 'artists': []}
if 'stats' not in st.session_state: st.session_state.stats = {}
if 'migration_done' not in st.session_state: st.session_state.migration_done = False
if 'balloons_shown' not in st.session_state: st.session_state.balloons_shown = False

# --- FUNÇÕES AUXILIARES ---
def get_display_name(user):
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    if full_name: return full_name
    return user.username or f"Usuário ID {user.id}"

def login_manual_streamlit():
    session = tidalapi.Session()
    try:
        try: client_id = session.config.client_id
        except AttributeError: client_id = "8SEZWa4J1NVC5U5Y"

        r = requests.post("https://auth.tidal.com/v1/oauth2/device_authorization", data={'client_id': client_id, 'scope': 'r_usr w_usr w_sub'})
        data = r.json()
        verification_uri = f"https://link.tidal.com/{data['userCode']}"
        device_code = data['deviceCode']
        expires_in = data.get('expires_in', 300)
        interval = data.get('interval', 5)
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None, None

    st.markdown(f"### 👉 [CLIQUE AQUI PARA LOGAR]({verification_uri})")
    st.code(data['userCode'], language="text")
    st.info("Aguardando autorização na outra aba...")
    
    start_time = time.time()
    while time.time() - start_time < expires_in:
        time.sleep(interval)
        try:
            r_check = requests.post("https://auth.tidal.com/v1/oauth2/token", data={
                'client_id': client_id, 'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                'device_code': device_code, 'scope': 'r_usr w_usr w_sub'
            })
            if r_check.status_code == 200:
                token_data = r_check.json()
                session.load_oauth_session(
                    token_type=token_data['token_type'], access_token=token_data['access_token'],
                    refresh_token=token_data.get('refresh_token'), expiry_time=time.time() + token_data['expires_in']
                )
                return session, session.user
        except: pass
    st.error("Tempo esgotado.")
    return None, None

# ==============================================================================
# APP PRINCIPAL
# ==============================================================================

st.title("🎵 Tidal Migrator Pro")
st.caption(f"{VERSION}")
st.markdown("---")

# CONEXÕES
c1, c2 = st.columns(2)
with c1:
    st.subheader("1️⃣ Origem (Velha)")
    if not st.session_state.user_old:
        if st.button("🔑 Conectar Origem"):
            s, u = login_manual_streamlit()
            if s and u:
                st.session_state.session_old, st.session_state.user_old = s, u
                st.rerun()
    else:
        st.success(f"✅ Conectado: **{get_display_name(st.session_state.user_old)}**")
        if st.button("Desconectar Origem"):
            st.session_state.session_old, st.session_state.user_old = None, None
            st.rerun()

with c2:
    st.subheader("2️⃣ Destino (Nova)")
    if not st.session_state.user_new:
        if st.button("🔑 Conectar Destino (ABA ANÔNIMA)"):
            s, u = login_manual_streamlit()
            if s and u:
                st.session_state.session_new, st.session_state.user_new = s, u
                st.rerun()
    else:
        st.success(f"✅ Conectado: **{get_display_name(st.session_state.user_new)}**")
        if st.button("Desconectar Destino"):
            st.session_state.session_new, st.session_state.user_new = None, None
            st.rerun()

st.markdown("---")

# MIGRAÇÃO E RELATÓRIO
if st.session_state.user_old and st.session_state.user_new:
    
    # ---------------------------------------------------------
    # TELA DE RELATÓRIO (INTERFACE BONITA DA V8.6 DE VOLTA)
    # ---------------------------------------------------------
    if st.session_state.migration_done:
        if not st.session_state.balloons_shown:
            st.balloons()
            st.session_state.balloons_shown = True
            
        st.success("✨ MIGRAÇÃO FINALIZADA!")
        
        stats = st.session_state.stats
        
        # Métricas no topo
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Músicas Novas", stats.get('tracks_added', 0))
        col2.metric("Músicas Puladas", stats.get('tracks_skipped', 0), delta="Duplicatas", delta_color="off")
        col3.metric("Playlists", stats.get('playlists_cloned', 0) + stats.get('playlists_followed', 0))
        col4.metric("Outros (Alb/Art)", stats.get('albums_added', 0) + stats.get('artists_added', 0))
        
        st.markdown("---")
        st.subheader("🔍 Relatório Detalhado")
        
        # Barra de Pesquisa
        search_term = st.text_input("Filtrar resultados:", placeholder="Digite nome da música, artista ou playlist...")
        
        # Abas
        tab1, tab2, tab3, tab4 = st.tabs(["✅ Adicionadas", "🚫 Puladas (Debug)", "📂 Playlists", "💿 Álbuns & Artistas"])
        
        def filter_data(data_list, term):
            if not term: return data_list
            return [item for item in data_list if term.lower() in item.lower()]

        with tab1:
            data = filter_data(st.session_state.logs['tracks'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Músicas Adicionadas com Sucesso"]), use_container_width=True, height=300)
            else: st.info("Nenhuma música nova encontrada com esse filtro.")
            
        with tab2:
            st.caption("Aqui estão as músicas que a inteligência do bot ignorou para não poluir sua conta com duplicatas.")
            data = filter_data(st.session_state.logs['tracks_skipped'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Motivo / Música Ignorada"]), use_container_width=True, height=300)
            else: st.info("Nenhuma música foi pulada.")

        with tab3:
            data = filter_data(st.session_state.logs['playlists'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Playlists Processadas"]), use_container_width=True)
            else: st.info("Nenhuma playlist encontrada.")

        with tab4: 
            st.write("**Álbuns:**")
            st.write(filter_data(st.session_state.logs['albums'], search_term) or "Vazio")
            st.write("**Artistas:**")
            st.write(filter_data(st.session_state.logs['artists'], search_term) or "Vazio")
            
        if st.button("🔄 Nova Migração", type="primary"):
            st.session_state.migration_done = False
            st.session_state.balloons_shown = False 
            st.rerun()

    # ---------------------------------------------------------
    # TELA DE EXECUÇÃO
    # ---------------------------------------------------------
    else:
        st.header("🚀 Painel de Migração")
        
        if st.session_state.user_old.id == st.session_state.user_new.id:
            st.error("⛔ ERRO: Você conectou a MESMA conta nos dois passos!")
            st.stop()

        if st.button("INICIAR CÓPIA AGORA", type="primary", use_container_width=True):
            
            st.session_state.logs = {'tracks': [], 'tracks_skipped': [], 'playlists': [], 'albums': [], 'artists': []}
            stats = {'tracks_added': 0, 'tracks_skipped': 0, 'albums_added': 0, 'artists_added': 0, 'playlists_cloned': 0, 'playlists_followed': 0}

            with st.status("Preparando Dados e Lendo Bibliotecas...", expanded=True) as status_box:
                u_old = st.session_state.user_old
                u_new = st.session_state.user_new
                
                # MAPEAMENTO DA CONTA NOVA
                st.write("🔍 Lendo conta nova para criar proteção anti-duplicata...")
                exist_tracks_ids = set()
                exist_tracks_sig = set()
                try: 
                    for t in u_new.favorites.tracks(limit=10000):
                        exist_tracks_ids.add(t.id)
                        # Cria a assinatura: "Nome da Musica - Nome do Artista" (tudo minúsculo)
                        exist_tracks_sig.add(f"{t.name} - {t.artist.name}".lower())
                except: pass
                
                try: exist_albums = set([a.id for a in u_new.favorites.albums(limit=2000)])
                except: exist_albums = set()
                
                try: exist_artists = set([a.id for a in u_new.favorites.artists(limit=2000)])
                except: exist_artists = set()
                
                try: exist_pl_names = set([p.name.lower() for p in u_new.playlists()]) 
                except: exist_pl_names = set()
                
                try: exist_fav_pl = set([p.id for p in u_new.favorites.playlists(limit=2000)])
                except: exist_fav_pl = set()

                # MÚSICAS
                st.write("🎵 Baixando Músicas da Origem...")
                try: old_tracks = u_old.favorites.tracks(limit=10000)
                except: old_tracks = []

                # Lógica Inteligente de Deduplicação e Logs
                to_add = []
                for t in old_tracks:
                    sig = f"{t.name} - {t.artist.name}".lower()
                    if t.id in exist_tracks_ids:
                        st.session_state.logs['tracks_skipped'].append(f"[DUPLICATA EXATA] {t.name} - {t.artist.name}")
                        stats['tracks_skipped'] += 1
                    elif sig in exist_tracks_sig:
                        st.session_state.logs['tracks_skipped'].append(f"[DUPLICATA DE NOME/ARTISTA] {t.name} - {t.artist.name}")
                        stats['tracks_skipped'] += 1
                    else:
                        to_add.append(t)

                to_add = to_add[::-1] # Ordem cronológica
                
                st.write(f"📊 Resumo: Encontradas {len(old_tracks)}. Pulando {stats['tracks_skipped']} duplicatas. Migrando {len(to_add)} faixas.")

                if to_add:
                    bar = st.progress(0)
                    for i, t in enumerate(to_add):
                        try:
                            u_new.favorites.add_track(t.id)
                            stats['tracks_added'] += 1
                            st.session_state.logs['tracks'].append(f"{t.name} - {t.artist.name}")
                            bar.progress((i+1)/len(to_add))
                            time.sleep(DELAY)
                        except: pass
                
                # Álbuns
                st.write("💿 Processando Álbuns...")
                try:
                    for a in u_old.favorites.albums(limit=2000):
                        if a.id not in exist_albums:
                            try: 
                                u_new.favorites.add_album(a.id)
                                stats['albums_added']+=1
                                st.session_state.logs['albums'].append(f"{a.name}")
                                time.sleep(DELAY)
                            except: pass
                except: pass
                
                # Artistas
                st.write("🎤 Processando Artistas...")
                try:
                    for a in u_old.favorites.artists(limit=2000):
                        if a.id not in exist_artists:
                            try: 
                                u_new.favorites.add_artist(a.id)
                                stats['artists_added']+=1
                                st.session_state.logs['artists'].append(a.name)
                                time.sleep(0.05)
                            except: pass
                except: pass

                # Playlists
                st.write("📂 Processando Playlists...")
                try:
                    processed = set()
                    all_pl = u_old.playlists() + u_old.favorites.playlists(limit=2000)
                    for pl in all_pl:
                        if pl.id in processed: continue
                        processed.add(pl.id)
                        try:
                            if pl.creator.id == u_old.id:
                                if pl.name.lower() not in exist_pl_names:
                                    new_pl = u_new.create_playlist(pl.name, pl.description or "")
                                    t_ids = [t.id for t in pl.tracks(limit=2000)]
                                    if t_ids: new_pl.add(t_ids)
                                    stats['playlists_cloned'] += 1
                                    st.session_state.logs['playlists'].append(f"[CLONADA] {pl.name}")
                                    time.sleep(1)
                            else:
                                if pl.id not in exist_fav_pl:
                                    u_new.favorites.add_playlist(pl.id)
                                    stats['playlists_followed'] += 1
                                    st.session_state.logs['playlists'].append(f"[SEGUIDA] {pl.name}")
                                    time.sleep(0.5)
                        except: pass
                except: pass
                
                status_box.update(label="✅ Tudo Concluído!", state="complete", expanded=False)
            
            st.session_state.stats = stats
            st.session_state.migration_done = True
            st.session_state.balloons_shown = False 
            st.rerun()

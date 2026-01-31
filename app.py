import streamlit as st
import tidalapi
import time
import requests
import pandas as pd

# --- CONFIGURAÇÕES ---
DELAY = 0.1
VERSION = "v8.5 (Full Unlocked)"

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
# Logs para busca
if 'logs' not in st.session_state: st.session_state.logs = {'tracks': [], 'playlists': [], 'albums': [], 'artists': []}
if 'stats' not in st.session_state: st.session_state.stats = {}
if 'migration_done' not in st.session_state: st.session_state.migration_done = False
# Trava para o balão não aparecer toda hora
if 'balloons_shown' not in st.session_state: st.session_state.balloons_shown = False

# --- FUNÇÕES AUXILIARES ---
def get_display_name(user):
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    if full_name: return full_name
    return user.username or f"Usuário ID {user.id}"

def login_manual_streamlit():
    session = tidalapi.Session()
    try:
        try:
            client_id = session.config.client_id
        except AttributeError:
            client_id = "8SEZWa4J1NVC5U5Y"

        url_auth = "https://auth.tidal.com/v1/oauth2/device_authorization"
        payload = {'client_id': client_id, 'scope': 'r_usr w_usr w_sub'}
        r = requests.post(url_auth, data=payload)
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
    
    url_token = "https://auth.tidal.com/v1/oauth2/token"
    start_time = time.time()
    
    while time.time() - start_time < expires_in:
        time.sleep(interval)
        payload_token = {
            'client_id': client_id,
            'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
            'device_code': device_code,
            'scope': 'r_usr w_usr w_sub'
        }
        try:
            r_check = requests.post(url_token, data=payload_token)
            if r_check.status_code == 200:
                token_data = r_check.json()
                session.load_oauth_session(
                    token_type=token_data['token_type'],
                    access_token=token_data['access_token'],
                    refresh_token=token_data.get('refresh_token'),
                    expiry_time=time.time() + token_data['expires_in']
                )
                return session, session.user
        except: pass
    st.error("Tempo esgotado.")
    return None, None

# ==============================================================================
# APP PRINCIPAL
# ==============================================================================

st.title("🎵 Tidal Migrator Pro")
st.caption(f"v{VERSION}")
st.markdown("---")

# 1. ORIGEM
st.subheader("1️⃣ Conta de Origem (Velha)")
if not st.session_state.user_old:
    if st.button("🔑 Conectar Origem"):
        s, u = login_manual_streamlit()
        if s and u:
            st.session_state.session_old = s
            st.session_state.user_old = u
            st.rerun()
else:
    u = st.session_state.user_old
    st.success(f"✅ Conectado: **{get_display_name(u)}**")
    if st.button("Desconectar Origem"):
        st.session_state.session_old = None
        st.session_state.user_old = None
        st.rerun()

st.markdown("---")

# 2. DESTINO
st.subheader("2️⃣ Conta de Destino (Nova)")
if not st.session_state.user_new:
    st.warning("⚠️ Use ABA ANÔNIMA para logar abaixo!")
    if st.button("🔑 Conectar Destino"):
        s, u = login_manual_streamlit()
        if s and u:
            st.session_state.session_new = s
            st.session_state.user_new = u
            st.rerun()
else:
    u = st.session_state.user_new
    st.success(f"✅ Conectado: **{get_display_name(u)}**")
    if st.button("Desconectar Destino"):
        st.session_state.session_new = None
        st.session_state.user_new = None
        st.rerun()

st.markdown("---")

# 3. MIGRAÇÃO
if st.session_state.user_old and st.session_state.user_new:
    
    # MODO RELATÓRIO (JÁ ACABOU)
    if st.session_state.migration_done:
        
        if not st.session_state.balloons_shown:
            st.balloons()
            st.session_state.balloons_shown = True
            
        st.success("✨ MIGRAÇÃO FINALIZADA!")
        
        # Painel de Métricas
        stats = st.session_state.stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Músicas Novas", stats.get('tracks_added', 0))
        c2.metric("Playlists", stats.get('playlists_cloned', 0) + stats.get('playlists_followed', 0))
        c3.metric("Álbuns", stats.get('albums_added', 0))
        c4.metric("Artistas", stats.get('artists_added', 0))
        
        st.markdown("---")
        st.subheader("🔍 Pesquisar no Relatório")
        
        search_term = st.text_input("Filtrar resultados:", placeholder="Digite nome da música ou playlist...")
        
        tab1, tab2, tab3, tab4 = st.tabs(["🎵 Músicas", "📂 Playlists", "💿 Álbuns", "🎤 Artistas"])
        
        def filter_data(data_list, term):
            if not term: return data_list
            return [item for item in data_list if term.lower() in item.lower()]

        with tab1:
            data = filter_data(st.session_state.logs['tracks'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Músicas Adicionadas"]), use_container_width=True, height=300)
            else: st.info("Nada encontrado.")
            
        with tab2:
            data = filter_data(st.session_state.logs['playlists'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Playlists Processadas"]), use_container_width=True)
            else: st.info("Nada encontrado.")

        with tab3:
            data = filter_data(st.session_state.logs['albums'], search_term)
            if data: st.write(data)
            else: st.info("Vazio.")

        with tab4:
            data = filter_data(st.session_state.logs['artists'], search_term)
            if data: st.write(data)
            else: st.info("Vazio.")
            
        if st.button("🔄 Fazer Nova Migração"):
            st.session_state.migration_done = False
            st.session_state.balloons_shown = False 
            st.rerun()

    # MODO EXECUÇÃO (AINDA NÃO COMEÇOU)
    else:
        st.header("🚀 Painel de Migração")
        
        if st.session_state.user_old.id == st.session_state.user_new.id:
            st.error("⛔ ERRO CRÍTICO: Mesma conta nos dois passos!")
            st.stop()

        if st.button("INICIAR CÓPIA AGORA", type="primary", use_container_width=True):
            
            # Zera logs e Status
            st.session_state.logs = {'tracks': [], 'playlists': [], 'albums': [], 'artists': []}
            stats = {
                'tracks_added': 0, 'tracks_skipped': 0,
                'albums_added': 0, 'artists_added': 0,
                'playlists_cloned': 0, 'playlists_followed': 0
            }

            with st.spinner("Analisando bibliotecas... (Lendo TUDO, pode demorar!)"):
                u_old = st.session_state.user_old
                u_new = st.session_state.user_new
                
                # --- CORREÇÃO IMPORTANTE: limit=None ---
                # Pega tudo o que já existe na nova para comparar
                exist_tracks = set([t.id for t in u_new.favorites.tracks(limit=None)])
                exist_albums = set([a.id for a in u_new.favorites.albums(limit=None)])
                exist_artists = set([a.id for a in u_new.favorites.artists(limit=None)])
                exist_pl_names = set([p.name for p in u_new.playlists() if p.creator.id == u_new.id])
                exist_fav_pl = set([p.id for p in u_new.favorites.playlists(limit=None)])

            # MÚSICAS
            st.write("🎵 Baixando TODAS as músicas da conta antiga...")
            # --- CORREÇÃO IMPORTANTE: limit=None ---
            old_tracks = u_old.favorites.tracks(limit=None)
            
            # Lógica: Só adiciona se o ID não existir na nova
            to_add = [t for t in old_tracks if t.id not in exist_tracks][::-1]
            stats['tracks_skipped'] = len(old_tracks) - len(to_add)
            
            st.write(f"Total encontrado: **{len(old_tracks)}** músicas. Novas para adicionar: **{len(to_add)}**")

            if to_add:
                bar = st.progress(0)
                txt = st.empty()
                for i, t in enumerate(to_add):
                    try:
                        u_new.favorites.add_track(t.id)
                        stats['tracks_added'] += 1
                        st.session_state.logs['tracks'].append(f"{t.name} - {t.artist.name}")
                        bar.progress((i+1)/len(to_add))
                        txt.caption(f"Adicionando: {t.name}")
                        time.sleep(DELAY)
                    except: pass
                txt.empty()
            
            # OUTROS
            with st.status("Finalizando Álbuns, Artistas e Playlists...", expanded=True):
                # Álbuns
                st.write("💿 Álbuns...")
                for a in u_old.favorites.albums(limit=None):
                    if a.id not in exist_albums:
                        try: 
                            u_new.favorites.add_album(a.id)
                            stats['albums_added']+=1
                            st.session_state.logs['albums'].append(f"{a.name} - {a.artist.name}")
                            time.sleep(DELAY)
                        except: pass
                
                # Artistas
                st.write("🎤 Artistas...")
                for a in u_old.favorites.artists(limit=None):
                    if a.id not in exist_artists:
                        try: 
                            u_new.favorites.add_artist(a.id)
                            stats['artists_added']+=1
                            st.session_state.logs['artists'].append(a.name)
                            time.sleep(0.05)
                        except: pass

                # Playlists
                st.write("📂 Playlists...")
                processed = set()
                # Pega todas (criadas e favoritas) da antiga
                all_pl = u_old.playlists() + u_old.favorites.playlists(limit=None)
                
                for pl in all_pl:
                    if pl.id in processed: continue
                    processed.add(pl.id)
                    try:
                        # Se a playlist é SUA (criada por você)
                        if pl.creator.id == u_old.id:
                            # Verifica duplicata pelo NOME
                            if pl.name not in exist_pl_names:
                                new_pl = u_new.create_playlist(pl.name, pl.description or "")
                                t_ids = [t.id for t in pl.tracks(limit=None)]
                                if t_ids: new_pl.add(t_ids)
                                stats['playlists_cloned'] += 1
                                st.session_state.logs['playlists'].append(f"[CLONADA] {pl.name}")
                                st.write(f"🛠️ Clonada: {pl.name}")
                                time.sleep(1)
                        # Se a playlist é de OUTRO (seguida)
                        else:
                            # Verifica duplicata pelo ID
                            if pl.id not in exist_fav_pl:
                                u_new.favorites.add_playlist(pl.id)
                                stats['playlists_followed'] += 1
                                st.session_state.logs['playlists'].append(f"[SEGUIDA] {pl.name}")
                                st.write(f"❤️ Seguindo: {pl.name}")
                                time.sleep(0.5)
                    except: pass
            
            st.session_state.stats = stats
            st.session_state.migration_done = True
            st.session_state.balloons_shown = False 
            st.rerun()

elif st.session_state.user_old or st.session_state.user_new:
    st.info("Conecte as duas contas acima.")
else:
    st.write("Faça login para começar.")

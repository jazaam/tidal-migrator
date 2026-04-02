import streamlit as st
import tidalapi
import time
import requests
import pandas as pd

# --- CONFIGURAÇÕES ---
DELAY = 0.2 # Aumentado para evitar bloqueio por "Too Many Requests" (HTTP 429)
VERSION = "v11.0 (Pagination Engine & Error Trace)"

st.set_page_config(page_title="Tidal Migrator Pro", page_icon="🎵", layout="centered")

def local_css():
    st.markdown("""
        <style>
        .stProgress > div > div > div > div { background-color: #00ebc7; }
        .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #00ebc7; }
        </style>
        """, unsafe_allow_html=True)
local_css()

if 'user_old' not in st.session_state: st.session_state.user_old = None
if 'user_new' not in st.session_state: st.session_state.user_new = None
if 'session_old' not in st.session_state: st.session_state.session_old = None
if 'session_new' not in st.session_state: st.session_state.session_new = None

if 'logs' not in st.session_state: 
    st.session_state.logs = {'tracks': [], 'tracks_skipped': [], 'playlists': [], 'albums': [], 'artists': []}
if 'stats' not in st.session_state: st.session_state.stats = {}
if 'migration_done' not in st.session_state: st.session_state.migration_done = False
if 'balloons_shown' not in st.session_state: st.session_state.balloons_shown = False

def get_display_name(user):
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return full_name if full_name else user.username or f"Usuário ID {user.id}"

# --- MOTOR DE PAGINAÇÃO (BURLA O LIMITE DE 200 ITENS) ---
def fetch_all_paginated(api_func, chunk_size=100):
    all_items = []
    offset = 0
    while True:
        try:
            chunk = api_func(limit=chunk_size, offset=offset)
            if not chunk: 
                break
            all_items.extend(chunk)
            offset += len(chunk)
            if len(chunk) < chunk_size: 
                break
        except Exception as e:
            st.error(f"Erro ao paginar na posição {offset}: {e}")
            break
    return all_items

def login_manual_streamlit():
    session = tidalapi.Session()
    try:
        try: client_id = session.config.client_id
        except AttributeError: client_id = "8SEZWa4J1NVC5U5Y"

        r = requests.post("https://auth.tidal.com/v1/oauth2/device_authorization", data={'client_id': client_id, 'scope': 'r_usr w_usr w_sub'})
        data = r.json()
        expires_in = data.get('expires_in', 300)
        interval = data.get('interval', 5)
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None, None

    st.markdown(f"### 👉 [CLIQUE AQUI PARA LOGAR](https://link.tidal.com/{data['userCode']})")
    st.code(data['userCode'], language="text")
    st.info("Aguardando autorização na outra aba...")
    
    start_time = time.time()
    while time.time() - start_time < expires_in:
        time.sleep(interval)
        try:
            r_check = requests.post("https://auth.tidal.com/v1/oauth2/token", data={
                'client_id': client_id, 'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                'device_code': data['deviceCode'], 'scope': 'r_usr w_usr w_sub'
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
st.title("🎵 Tidal Migrator Pro")
st.caption(f"{VERSION}")
st.markdown("---")

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

if st.session_state.user_old and st.session_state.user_new:
    
    if st.session_state.migration_done:
        if not st.session_state.balloons_shown:
            st.balloons()
            st.session_state.balloons_shown = True
            
        st.success("✨ MIGRAÇÃO FINALIZADA!")
        stats = st.session_state.stats
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Músicas Novas", stats.get('tracks_added', 0))
        col2.metric("Músicas Puladas", stats.get('tracks_skipped', 0), delta="Duplicatas / Erros", delta_color="off")
        col3.metric("Playlists", stats.get('playlists_cloned', 0) + stats.get('playlists_followed', 0))
        col4.metric("Outros (Alb/Art)", stats.get('albums_added', 0) + stats.get('artists_added', 0))
        
        st.markdown("---")
        st.subheader("🔍 Relatório Técnico")
        
        search_term = st.text_input("Filtrar resultados:", placeholder="Digite nome da música, artista ou erro...")
        tab1, tab2, tab3, tab4 = st.tabs(["✅ Adicionadas", "🚫 Logs & Erros", "📂 Playlists", "💿 Álbuns & Artistas"])
        
        def filter_data(data_list, term):
            return [item for item in data_list if term.lower() in item.lower()] if term else data_list

        with tab1:
            data = filter_data(st.session_state.logs['tracks'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Músicas Adicionadas"]), use_container_width=True, height=300)
            else: st.info("Nenhuma música.")
            
        with tab2:
            st.caption("Logs de Duplicatas e Erros de API (Crucial para auditoria).")
            data = filter_data(st.session_state.logs['tracks_skipped'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Log do Sistema"]), use_container_width=True, height=300)
            else: st.info("Limpo.")

        with tab3:
            data = filter_data(st.session_state.logs['playlists'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Playlists Processadas"]), use_container_width=True)
            else: st.info("Vazio.")

        with tab4: 
            st.write("**Álbuns:**", filter_data(st.session_state.logs['albums'], search_term))
            st.write("**Artistas:**", filter_data(st.session_state.logs['artists'], search_term))
            
        if st.button("🔄 Nova Migração", type="primary"):
            st.session_state.migration_done = False
            st.session_state.balloons_shown = False 
            st.rerun()

    else:
        st.header("🚀 Painel de Execução")
        
        if st.session_state.user_old.id == st.session_state.user_new.id:
            st.error("⛔ ERRO: Mesma conta logada nos dois passos.")
            st.stop()

        if st.button("INICIAR EXTRAÇÃO TOTAL", type="primary", use_container_width=True):
            
            st.session_state.logs = {'tracks': [], 'tracks_skipped': [], 'playlists': [], 'albums': [], 'artists': []}
            stats = {'tracks_added': 0, 'tracks_skipped': 0, 'albums_added': 0, 'artists_added': 0, 'playlists_cloned': 0, 'playlists_followed': 0}

            with st.status("Processamento em Lote...", expanded=True) as status_box:
                u_old = st.session_state.user_old
                u_new = st.session_state.user_new
                
                st.write("🔍 Extraindo inventário base da conta Destino...")
                exist_tracks_ids = set()
                exist_tracks_sig = set()
                
                # Paginação na conta nova
                existing_tracks_raw = fetch_all_paginated(u_new.favorites.tracks)
                for t in existing_tracks_raw:
                    exist_tracks_ids.add(t.id)
                    exist_tracks_sig.add(f"{t.name} - {t.artist.name}".lower())
                
                exist_albums = set([a.id for a in fetch_all_paginated(u_new.favorites.albums)])
                exist_artists = set([a.id for a in fetch_all_paginated(u_new.favorites.artists)])
                
                exist_pl_names = set()
                try: exist_pl_names = set([p.name.lower() for p in u_new.playlists()]) 
                except Exception as e: st.session_state.logs['tracks_skipped'].append(f"[ERRO API] Falha ler nomes playlists: {e}")
                
                exist_fav_pl = set([p.id for p in fetch_all_paginated(u_new.favorites.playlists)])

                # MÚSICAS DA CONTA VELHA (AGORA COM PAGINAÇÃO FORÇADA)
                st.write("🎵 Extraindo TODAS as músicas da Origem (Paginação ativa)...")
                old_tracks = fetch_all_paginated(u_old.favorites.tracks)
                
                to_add = []
                for t in old_tracks:
                    sig = f"{t.name} - {t.artist.name}".lower()
                    if t.id in exist_tracks_ids:
                        st.session_state.logs['tracks_skipped'].append(f"[PULADO - ID] {t.name} - {t.artist.name}")
                        stats['tracks_skipped'] += 1
                    elif sig in exist_tracks_sig:
                        st.session_state.logs['tracks_skipped'].append(f"[PULADO - NOME] {t.name} - {t.artist.name}")
                        stats['tracks_skipped'] += 1
                    else:
                        to_add.append(t)

                to_add = to_add[::-1] # Ordem cronológica original
                st.write(f"📊 Volume lido: {len(old_tracks)}. Carga para inserção: {len(to_add)}.")

                if to_add:
                    bar = st.progress(0)
                    for i, t in enumerate(to_add):
                        try:
                            u_new.favorites.add_track(t.id)
                            stats['tracks_added'] += 1
                            st.session_state.logs['tracks'].append(f"{t.name} - {t.artist.name}")
                            bar.progress((i+1)/len(to_add))
                            time.sleep(DELAY) # Proteção contra limite de requisição
                        except Exception as e:
                            st.session_state.logs['tracks_skipped'].append(f"[ERRO ADD TRACK] {t.name}: {e}")
                            stats['tracks_skipped'] += 1
                
                st.write("💿 Processando Álbuns...")
                for a in fetch_all_paginated(u_old.favorites.albums):
                    if a.id not in exist_albums:
                        try: 
                            u_new.favorites.add_album(a.id)
                            stats['albums_added']+=1
                            st.session_state.logs['albums'].append(f"{a.name}")
                            time.sleep(DELAY)
                        except Exception as e:
                            st.session_state.logs['tracks_skipped'].append(f"[ERRO ÁLBUM] {a.name}: {e}")
                
                st.write("🎤 Processando Artistas...")
                for a in fetch_all_paginated(u_old.favorites.artists):
                    if a.id not in exist_artists:
                        try: 
                            u_new.favorites.add_artist(a.id)
                            stats['artists_added']+=1
                            st.session_state.logs['artists'].append(a.name)
                            time.sleep(DELAY)
                        except Exception as e:
                            st.session_state.logs['tracks_skipped'].append(f"[ERRO ARTISTA] {a.name}: {e}")

                st.write("📂 Processando Playlists...")
                processed = set()
                
                try:
                    # Captura explícita para evitar falhas silenciosas
                    my_old_pls = u_old.playlists()
                    fav_old_pls = fetch_all_paginated(u_old.favorites.playlists)
                    all_pl = my_old_pls + fav_old_pls
                    
                    for pl in all_pl:
                        if pl.id in processed: continue
                        processed.add(pl.id)
                        
                        try:
                            if pl.creator.id == u_old.id:
                                if pl.name.lower() not in exist_pl_names:
                                    new_pl = u_new.create_playlist(pl.name, pl.description or "")
                                    # Paginando também as faixas internas da playlist
                                    t_ids = [t.id for t in fetch_all_paginated(pl.tracks)]
                                    if t_ids: new_pl.add(t_ids)
                                    stats['playlists_cloned'] += 1
                                    st.session_state.logs['playlists'].append(f"[CLONADA] {pl.name}")
                                    time.sleep(1)
                                else:
                                    st.session_state.logs['tracks_skipped'].append(f"[PLAYLIST IGNORADA] Já existe '{pl.name}'")
                            else:
                                if pl.id not in exist_fav_pl:
                                    u_new.favorites.add_playlist(pl.id)
                                    stats['playlists_followed'] += 1
                                    st.session_state.logs['playlists'].append(f"[SEGUIDA] {pl.name}")
                                    time.sleep(0.5)
                        except Exception as e:
                            st.session_state.logs['tracks_skipped'].append(f"[ERRO PLAYLIST] {pl.name}: {e}")
                except Exception as e:
                    st.session_state.logs['tracks_skipped'].append(f"[ERRO GERAL PLAYLISTS]: {e}")
                
                status_box.update(label="Processamento Concluído", state="complete", expanded=False)
            
            st.session_state.stats = stats
            st.session_state.migration_done = True
            st.session_state.balloons_shown = False 
            st.rerun()

import streamlit as st
import tidalapi
import time
import requests
import pandas as pd

# --- CONFIGURAÇÕES ---
DELAY = 0.2
VERSION = "v13.0 (Masterpiece - API Sync & Debug Cofre)"

st.set_page_config(page_title="Tidal Migrator Pro", page_icon="🎵", layout="centered")

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

# SISTEMA DE LOGS ESTRUTURADO E PERSISTENTE
if 'logs' not in st.session_state: 
    st.session_state.logs = {
        'success': [],   # Tudo que deu certo
        'skipped': [],   # Tudo que foi pulado por duplicata
        'errors': []     # Erros Fatais (400, 429, timeouts)
    }
if 'stats' not in st.session_state: st.session_state.stats = {}
if 'migration_done' not in st.session_state: st.session_state.migration_done = False

def get_display_name(user):
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return full_name if full_name else user.username or f"Usuário ID {user.id}"

# --- MOTOR DE EXTRAÇÃO BLINDADO (PAGINAÇÃO MAX 50) ---
def fetch_paginated(log_label, api_function):
    """
    Busca dados na API burlando o limite padrão, mas respeitando o teto de 50 itens 
    por requisição para evitar o HTTP 400 Bad Request nos endpoints v2 do Tidal.
    """
    items = []
    offset = 0
    limit = 50 
    
    while True:
        try:
            chunk = api_function(limit=limit, offset=offset)
            if not chunk:
                break
            items.extend(chunk)
            offset += len(chunk)
            if len(chunk) < limit:
                break
        except Exception as e:
            error_msg = str(e)
            if offset == 0:
                # Se falhou no offset 0, tenta sem limite (Fallback nativo do python-tidal)
                st.session_state.logs['errors'].append(f"[{log_label}] Erro na paginação inicial ({error_msg}). Tentando Fallback Nativo.")
                try:
                    return api_function()
                except Exception as e_fallback:
                    st.session_state.logs['errors'].append(f"[{log_label}] FALHA FATAL no Fallback: {e_fallback}")
                    break
            else:
                st.session_state.logs['errors'].append(f"[{log_label}] API bloqueou a leitura no item {offset}: {error_msg}")
                break
    return items

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
        st.success("✨ MIGRAÇÃO FINALIZADA!")
        stats = st.session_state.stats
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Adicionados", len(st.session_state.logs['success']))
        col2.metric("Duplicatas Puladas", len(st.session_state.logs['skipped']))
        col3.metric("Erros na API", len(st.session_state.logs['errors']))
        col4.metric("Playlists Tratadas", stats.get('playlists', 0))
        
        st.markdown("---")
        st.subheader("🔍 Console de Auditoria")
        
        search_term = st.text_input("Filtrar logs:", placeholder="Pesquise música, artista ou erro...")
        tab1, tab2, tab3 = st.tabs(["✅ Sucesso", "⏭️ Pulados", "🚨 Erros Fatais (Debug)"])
        
        def filter_data(data_list, term):
            return [item for item in data_list if term.lower() in item.lower()] if term else data_list

        with tab1:
            data = filter_data(st.session_state.logs['success'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Status / Ação"]), use_container_width=True, height=400)
            else: st.info("Nada registrado.")
            
        with tab2:
            st.caption("Itens ignorados pelo motor inteligente para proteger sua conta contra duplicação.")
            data = filter_data(st.session_state.logs['skipped'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Motivo / Item"]), use_container_width=True, height=400)
            else: st.info("Nenhuma duplicata.")

        with tab3:
            st.caption("Qualquer recusa do servidor Tidal (Bad Request, Timeout) ficará gravada aqui.")
            data = filter_data(st.session_state.logs['errors'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Traceback Crítico"]), use_container_width=True, height=400)
            else: st.success("Nenhum erro fatal! Sistema operou 100%.")
            
        if st.button("🔄 Executar Novamente", type="primary"):
            st.session_state.migration_done = False
            st.rerun()

    else:
        st.header("🚀 Painel de Controle de Execução")
        
        if st.session_state.user_old.id == st.session_state.user_new.id:
            st.error("⛔ ERRO CRÍTICO: Mesma conta detectada na Origem e Destino.")
            st.stop()

        if st.button("INICIAR EXTRAÇÃO E MIGRAÇÃO", type="primary", use_container_width=True):
            
            # Resetando estado dos logs para nova execução
            st.session_state.logs = {'success': [], 'skipped': [], 'errors': []}
            stats = {'playlists': 0}

            with st.status("Executando Protocolo de Sincronização (Aguarde...)", expanded=True) as status_box:
                u_old = st.session_state.user_old
                u_new = st.session_state.user_new
                
                # --- BASE DESTINO (CONSTRUINDO A BARREIRA ANTI-DUPLICAÇÃO) ---
                st.write("🔍 Mapeando inventário da conta Destino (Nova)...")
                exist_tracks_ids, exist_tracks_sig = set(), set()
                
                existing_tracks_raw = fetch_paginated("Destino Tracks", u_new.favorites.tracks)
                for t in existing_tracks_raw:
                    try:
                        exist_tracks_ids.add(t.id)
                        exist_tracks_sig.add(f"{t.name} - {t.artist.name}".lower())
                    except: pass
                
                exist_albums = set([a.id for a in fetch_paginated("Destino Álbuns", u_new.favorites.albums)])
                exist_artists = set([a.id for a in fetch_paginated("Destino Artistas", u_new.favorites.artists)])
                exist_fav_pl = set([p.id for p in fetch_paginated("Destino Playlists Favoritas", u_new.favorites.playlists)])
                
                # Playlists Nomes
                exist_pl_names = set()
                try: 
                    exist_pl_names = set([p.name.lower() for p in fetch_paginated("Destino Playlists Nomes", u_new.playlists)])
                except Exception as e:
                    st.session_state.logs['errors'].append(f"[Mapeamento] Falha ao ler nomes de playlists destino: {e}")

                # --- EXTRAÇÃO DA ORIGEM ---
                st.write("🎵 Extraindo Músicas da conta Origem (Velha)...")
                old_tracks = fetch_paginated("Origem Tracks", u_old.favorites.tracks)
                
                to_add = []
                for t in old_tracks:
                    try:
                        sig = f"{t.name} - {t.artist.name}".lower()
                        if t.id in exist_tracks_ids:
                            st.session_state.logs['skipped'].append(f"[PULADO: ID EXATO] {t.name} - {t.artist.name}")
                        elif sig in exist_tracks_sig:
                            st.session_state.logs['skipped'].append(f"[PULADO: ASSINATURA NOME] {t.name} - {t.artist.name}")
                        else:
                            to_add.append(t)
                    except Exception as e:
                        st.session_state.logs['errors'].append(f"[Verificação de Duplicata] Erro ao ler track velha: {e}")

                to_add = to_add[::-1] # Inverte para inserir as mais antigas primeiro
                st.write(f"📊 Volume processado: {len(old_tracks)} lidas. {len(to_add)} novas enviadas para inserção.")

                if to_add:
                    bar = st.progress(0)
                    for i, t in enumerate(to_add):
                        try:
                            u_new.favorites.add_track(t.id)
                            st.session_state.logs['success'].append(f"[MÚSICA ADD] {t.name} - {t.artist.name}")
                            bar.progress((i+1)/len(to_add))
                            time.sleep(DELAY)
                        except Exception as e:
                            st.session_state.logs['errors'].append(f"[FALHA INSERÇÃO MÚSICA] {t.name}: {e}")
                
                # --- ÁLBUNS E ARTISTAS ---
                st.write("💿 Processando Álbuns e Artistas...")
                for a in fetch_paginated("Origem Álbuns", u_old.favorites.albums):
                    if a.id not in exist_albums:
                        try: 
                            u_new.favorites.add_album(a.id)
                            st.session_state.logs['success'].append(f"[ÁLBUM ADD] {a.name}")
                            time.sleep(DELAY)
                        except Exception as e:
                            st.session_state.logs['errors'].append(f"[FALHA INSERÇÃO ÁLBUM] {a.name}: {e}")
                    else:
                        st.session_state.logs['skipped'].append(f"[PULADO: ÁLBUM] {a.name}")
                
                for a in fetch_paginated("Origem Artistas", u_old.favorites.artists):
                    if a.id not in exist_artists:
                        try: 
                            u_new.favorites.add_artist(a.id)
                            st.session_state.logs['success'].append(f"[ARTISTA ADD] {a.name}")
                            time.sleep(DELAY)
                        except Exception as e:
                            st.session_state.logs['errors'].append(f"[FALHA INSERÇÃO ARTISTA] {a.name}: {e}")
                    else:
                        st.session_state.logs['skipped'].append(f"[PULADO: ARTISTA] {a.name}")

                # --- PLAYLISTS ---
                st.write("📂 Processando Playlists...")
                processed = set()
                
                my_old_pls = fetch_paginated("Origem Minhas Playlists", u_old.playlists)
                fav_old_pls = fetch_paginated("Origem Playlists Favoritas", u_old.favorites.playlists)
                all_pl = my_old_pls + fav_old_pls
                
                for pl in all_pl:
                    if pl.id in processed: continue
                    processed.add(pl.id)
                    
                    try:
                        if pl.creator.id == u_old.id:
                            if pl.name.lower() not in exist_pl_names:
                                new_pl = u_new.create_playlist(pl.name, pl.description or "")
                                tracks_raw = fetch_paginated(f"Origem Tracks da Playlist {pl.name}", pl.tracks)
                                t_ids = [t.id for t in tracks_raw]
                                if t_ids: new_pl.add(t_ids)
                                st.session_state.logs['success'].append(f"[PLAYLIST CLONADA] {pl.name}")
                                stats['playlists'] += 1
                                time.sleep(1)
                            else:
                                st.session_state.logs['skipped'].append(f"[PULADO: PLAYLIST NOME IGUAL] {pl.name}")
                        else:
                            if pl.id not in exist_fav_pl:
                                u_new.favorites.add_playlist(pl.id)
                                st.session_state.logs['success'].append(f"[PLAYLIST SEGUIDA] {pl.name}")
                                stats['playlists'] += 1
                                time.sleep(0.5)
                            else:
                                st.session_state.logs['skipped'].append(f"[PULADO: PLAYLIST JÁ SEGUIDA] {pl.name}")
                    except Exception as e:
                        st.session_state.logs['errors'].append(f"[FALHA CLONAGEM PLAYLIST] {pl.name}: {e}")
                
                status_box.update(label="✅ Operação Concluída com Sucesso", state="complete", expanded=False)
            
            st.session_state.stats = stats
            st.session_state.migration_done = True
            st.rerun()

import streamlit as st
import tidalapi
import time
import requests
import pandas as pd

# --- CONFIGURAÇÕES ---
DELAY = 0.2
VERSION = "v14.0 (God Mode - Full Dashboard & 4-Tier Debug)"

st.set_page_config(page_title="Tidal Migrator Pro", page_icon="🎵", layout="wide")

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

if 'logs' not in st.session_state: 
    st.session_state.logs = {'success': [], 'skipped': [], 'warnings': [], 'errors': []}
if 'stats' not in st.session_state: st.session_state.stats = {}
if 'scan_data' not in st.session_state: st.session_state.scan_data = None
if 'migration_done' not in st.session_state: st.session_state.migration_done = False

def get_display_name(user):
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"ID {user.id}"

# --- MOTOR DE EXTRAÇÃO BLINDADO ---
def fetch_data(log_label, api_function, supports_pagination=True):
    if not supports_pagination:
        try:
            return api_function()
        except Exception as e:
            st.session_state.logs['errors'].append(f"[{log_label}] ERRO FATAL de Leitura: {e}")
            return []
            
    items = []
    offset = 0
    limit = 100 
    
    while True:
        try:
            chunk = api_function(limit=limit, offset=offset)
            if not chunk: break
            items.extend(chunk)
            offset += len(chunk)
            if len(chunk) < limit: break
        except TypeError as te:
            if 'limit' in str(te):
                st.session_state.logs['warnings'].append(f"[{log_label}] API recusou paginação. Usando extração em bloco único.")
                try:
                    return api_function()
                except Exception as e_fallback:
                    st.session_state.logs['errors'].append(f"[{log_label}] FALHA no Bloco Único: {e_fallback}")
                    break
            else:
                st.session_state.logs['errors'].append(f"[{log_label}] Erro interno de tipo: {te}")
                break
        except Exception as e:
            st.session_state.logs['errors'].append(f"[{log_label}] Corte do Servidor na posição {offset}: {e}")
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
        scan = st.session_state.scan_data
        
        # --- DASHBOARD DE CIMA (STATUS RÁPIDO) ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Adicionados c/ Sucesso", len(st.session_state.logs['success']))
        col2.metric("Duplicatas Puladas", len(st.session_state.logs['skipped']))
        col3.metric("Avisos Internos", len(st.session_state.logs['warnings']))
        col4.metric("Erros Fatais", len(st.session_state.logs['errors']))
        
        st.markdown("---")
        
        # --- PANORAMA DAS CONTAS ---
        st.subheader("📊 Panorama das Contas (Escâner)")
        st.dataframe(pd.DataFrame({
            "Categoria": ["Músicas Salvas", "Álbuns Salvos", "Artistas Seguidos", "Playlists (Todas)"],
            "Tinha na Origem (Velha)": [scan['old_tracks'], scan['old_albums'], scan['old_artists'], scan['old_pls']],
            "Tem na Destino (Nova)": [scan['new_tracks'], scan['new_albums'], scan['new_artists'], scan['new_pls']]
        }), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # --- LOGS DETALHADOS 4-TIER ---
        st.subheader("🔍 Console de Auditoria Profunda")
        search_term = st.text_input("Filtrar logs:", placeholder="Pesquise música, artista ou erro...")
        
        tab1, tab2, tab3, tab4 = st.tabs(["✅ Sucesso", "⏭️ Pulados (Já Existia)", "⚠️ Avisos (Sistema)", "🚨 Erros Fatais"])
        
        def filter_data(data_list, term):
            return [item for item in data_list if term.lower() in item.lower()] if term else data_list

        with tab1:
            data = filter_data(st.session_state.logs['success'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Item Processado com Êxito"]), use_container_width=True, height=300)
            else: st.info("Nada registrado.")
            
        with tab2:
            st.caption("Itens ignorados pelo motor inteligente porque JÁ EXISTEM na conta Nova.")
            data = filter_data(st.session_state.logs['skipped'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Motivo / Item Duplicado"]), use_container_width=True, height=300)
            else: st.info("Nenhuma duplicata.")
            
        with tab3:
            st.caption("Adaptações que o código precisou fazer para o Tidal não bloquear a conexão (Não afeta o resultado).")
            data = filter_data(st.session_state.logs['warnings'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Aviso Interno da API"]), use_container_width=True, height=300)
            else: st.success("Sistema rodou sem precisar de adaptações.")

        with tab4:
            st.caption("Recusas severas do servidor Tidal (Timeout, Banned, Permissão Negada). Se algo não foi, o motivo está aqui.")
            data = filter_data(st.session_state.logs['errors'], search_term)
            if data: st.dataframe(pd.DataFrame(data, columns=["Traceback Crítico (API)"]), use_container_width=True, height=300)
            else: st.success("Zero Erros Fatais! O caminho está livre.")
            
        if st.button("🔄 Reiniciar / Refazer Verificação", type="primary"):
            st.session_state.migration_done = False
            st.rerun()

    else:
        st.header("🚀 Painel de Controle de Execução")
        
        if st.session_state.user_old.id == st.session_state.user_new.id:
            st.error("⛔ ERRO CRÍTICO: Mesma conta detectada na Origem e Destino.")
            st.stop()

        if st.button("INICIAR ESCÂNER E MIGRAÇÃO", type="primary", use_container_width=True):
            
            st.session_state.logs = {'success': [], 'skipped': [], 'warnings': [], 'errors': []}
            
            with st.status("🕵️ Escaneando Contas e Migrando... (Não feche a aba)", expanded=True) as status_box:
                u_old = st.session_state.user_old
                u_new = st.session_state.user_new
                
                # --- PASSO 1: O GRANDE ESCÂNER ---
                st.write("🔍 Lendo Biblioteca Destino (Nova)...")
                new_tracks_raw = fetch_data("Destino Tracks", u_new.favorites.tracks)
                new_albums_raw = fetch_data("Destino Álbuns", u_new.favorites.albums)
                new_artists_raw = fetch_data("Destino Artistas", u_new.favorites.artists)
                new_pls_raw = fetch_data("Destino Minhas Playlists", u_new.playlists, supports_pagination=False)
                new_fav_pls_raw = fetch_data("Destino Playlists Favoritas", u_new.favorites.playlists)
                
                st.write("🔍 Lendo Biblioteca Origem (Velha)...")
                old_tracks_raw = fetch_data("Origem Tracks", u_old.favorites.tracks)
                old_albums_raw = fetch_data("Origem Álbuns", u_old.favorites.albums)
                old_artists_raw = fetch_data("Origem Artistas", u_old.favorites.artists)
                old_pls_raw = fetch_data("Origem Minhas Playlists", u_old.playlists, supports_pagination=False)
                old_fav_pls_raw = fetch_data("Origem Playlists Favoritas", u_old.favorites.playlists)
                
                # Salvando métricas para o Dashboard
                st.session_state.scan_data = {
                    'old_tracks': len(old_tracks_raw), 'old_albums': len(old_albums_raw), 
                    'old_artists': len(old_artists_raw), 'old_pls': len(old_pls_raw) + len(old_fav_pls_raw),
                    'new_tracks': len(new_tracks_raw), 'new_albums': len(new_albums_raw), 
                    'new_artists': len(new_artists_raw), 'new_pls': len(new_pls_raw) + len(new_fav_pls_raw)
                }

                # --- PASSO 2: CONSTRUINDO A BARREIRA ---
                exist_tracks_ids = set([t.id for t in new_tracks_raw])
                exist_tracks_sig = set([f"{t.name} - {t.artist.name}".lower() for t in new_tracks_raw])
                exist_albums = set([a.id for a in new_albums_raw])
                exist_artists = set([a.id for a in new_artists_raw])
                exist_pl_names = set([p.name.lower() for p in new_pls_raw])
                exist_fav_pl = set([p.id for p in new_fav_pls_raw])

                # --- PASSO 3: MÚSICAS ---
                st.write(f"🎵 Injetando Músicas (Analisando {len(old_tracks_raw)} itens)...")
                to_add = []
                for t in old_tracks_raw:
                    try:
                        sig = f"{t.name} - {t.artist.name}".lower()
                        if t.id in exist_tracks_ids:
                            st.session_state.logs['skipped'].append(f"[MÚSICA - JÁ EXISTE ID] {t.name} - {t.artist.name}")
                        elif sig in exist_tracks_sig:
                            st.session_state.logs['skipped'].append(f"[MÚSICA - NOME DUPLICADO] {t.name} - {t.artist.name}")
                        else:
                            to_add.append(t)
                    except Exception as e:
                        st.session_state.logs['errors'].append(f"[Verificação Duplicata Track] Erro: {e}")

                to_add = to_add[::-1] # Ordem cronológica
                if to_add:
                    bar = st.progress(0)
                    for i, t in enumerate(to_add):
                        try:
                            u_new.favorites.add_track(t.id)
                            st.session_state.logs['success'].append(f"[MÚSICA GRAVADA] {t.name} - {t.artist.name}")
                            bar.progress((i+1)/len(to_add))
                            time.sleep(DELAY)
                        except Exception as e:
                            st.session_state.logs['errors'].append(f"[FALHA INSERÇÃO MÚSICA] {t.name}: {e}")
                
                # --- PASSO 4: ÁLBUNS E ARTISTAS ---
                st.write("💿 Processando Álbuns e Artistas...")
                for a in old_albums_raw:
                    if a.id not in exist_albums:
                        try: 
                            u_new.favorites.add_album(a.id)
                            st.session_state.logs['success'].append(f"[ÁLBUM GRAVADO] {a.name}")
                            time.sleep(DELAY)
                        except Exception as e:
                            st.session_state.logs['errors'].append(f"[FALHA INSERÇÃO ÁLBUM] {a.name}: {e}")
                    else:
                        st.session_state.logs['skipped'].append(f"[ÁLBUM - JÁ EXISTE] {a.name}")
                
                for a in old_artists_raw:
                    if a.id not in exist_artists:
                        try: 
                            u_new.favorites.add_artist(a.id)
                            st.session_state.logs['success'].append(f"[ARTISTA GRAVADO] {a.name}")
                            time.sleep(DELAY)
                        except Exception as e:
                            st.session_state.logs['errors'].append(f"[FALHA INSERÇÃO ARTISTA] {a.name}: {e}")
                    else:
                        st.session_state.logs['skipped'].append(f"[ARTISTA - JÁ EXISTE] {a.name}")

                # --- PASSO 5: PLAYLISTS ---
                st.write("📂 Clonando Playlists...")
                processed = set()
                all_pl = old_pls_raw + old_fav_pls_raw
                
                for pl in all_pl:
                    if pl.id in processed: continue
                    processed.add(pl.id)
                    
                    try:
                        if pl.creator.id == u_old.id:
                            if pl.name.lower() not in exist_pl_names:
                                new_pl = u_new.create_playlist(pl.name, pl.description or "")
                                tracks_raw = fetch_data(f"Playlist {pl.name}", pl.tracks)
                                t_ids = [t.id for t in tracks_raw]
                                if t_ids: new_pl.add(t_ids)
                                st.session_state.logs['success'].append(f"[PLAYLIST CRIADA] {pl.name}")
                                time.sleep(1)
                            else:
                                st.session_state.logs['skipped'].append(f"[PLAYLIST - NOME JÁ EXISTE] {pl.name}")
                        else:
                            if pl.id not in exist_fav_pl:
                                u_new.favorites.add_playlist(pl.id)
                                st.session_state.logs['success'].append(f"[PLAYLIST SEGUIDA] {pl.name}")
                                time.sleep(0.5)
                            else:
                                st.session_state.logs['skipped'].append(f"[PLAYLIST - JÁ SEGUIA] {pl.name}")
                    except Exception as e:
                        st.session_state.logs['errors'].append(f"[FALHA CLONAGEM PLAYLIST] {pl.name}: {e}")
                
                status_box.update(label="✅ Operação Concluída com Sucesso", state="complete", expanded=False)
            
            st.session_state.migration_done = True
            st.rerun()

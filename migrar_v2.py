import tidalapi
import sys
import time

# Configuração de segurança
DELAY = 0.2  # Tempo entre ações para não travar a API

def autenticar(nome):
    print(f"\n🔑 --- LOGIN: {nome} ---")
    session = tidalapi.Session()
    session.login_oauth_simple()
    if session.check_login():
        print(f"✅ Logado: {session.user.first_name} (ID: {session.user.id})")
        return session
    else:
        print("❌ Falha no login.")
        sys.exit(1)

def main():
    print("=== 🛡️ MIGRADOR SEGURO V2 (SEM DELETE) 🛡️ ===")
    
    # ---------------------------------------------------------
    # PASSO 1: CONTA VELHA (ORIGEM) - jazaam+tidal1
    # ---------------------------------------------------------
    print("\n👉 PASSO 1: Logue na CONTA VELHA (Origem: jazaam+tidal1)")
    print("   (Clique no link e autorize no navegador NORMAL)")
    session_old = autenticar("CONTA VELHA (Ler Dados)")
    
    # ---------------------------------------------------------
    # PASSO 2: CONTA NOVA (DESTINO) - jazaam+tidal2
    # ---------------------------------------------------------
    print("\n👉 PASSO 2: Logue na CONTA NOVA (Destino: jazaam+tidal2)")
    print("⚠️  ATENÇÃO: Copie o link abaixo e abra em uma ABA ANÔNIMA!")
    session_new = autenticar("CONTA NOVA (Gravar Dados)")

    print("\n📦 Iniciando transferência... (Nada será apagado)")
    user_old = session_old.user
    user_new = session_new.user

    # 1. TRANSFERIR LIKES (MÚSICAS)
    tracks = user_old.favorites.tracks()
    total = len(tracks)
    print(f"\n🎵 Encontradas {total} músicas curtidas na conta velha.")
    
    for i, track in enumerate(tracks):
        try:
            # COMANDO DE LEITURA (Old) -> COMANDO DE ESCRITA (New)
            user_new.favorites.add_track(track.id)
            sys.stdout.write(f"\r   Processando: {i+1}/{total}")
            sys.stdout.flush()
            time.sleep(DELAY)
        except Exception:
            pass

    # 2. TRANSFERIR ARTISTAS
    artists = user_old.favorites.artists()
    print(f"\n\n🎤 Transferindo {len(artists)} artistas...")
    for artist in artists:
        try:
            user_new.favorites.add_artist(artist.id)
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(DELAY)
        except: pass

    # 3. TRANSFERIR TODAS AS PLAYLISTS (Criadas e Salvas)
    print(f"\n\n📂 Transferindo Playlists...")
    playlists = user_old.playlists() # Pega TUDO (Criadas + Salvas)
    
    for pl in playlists:
        print(f"\n   💿 Copiando Playlist: '{pl.name}'")
        try:
            # 1. Cria uma playlist nova na conta destino com o mesmo nome
            new_pl = user_new.create_playlist(pl.name, pl.description if pl.description else "")
            
            # 2. Pega as músicas da playlist velha
            tracks_in_pl = pl.tracks()
            track_ids = [t.id for t in tracks_in_pl]
            
            if track_ids:
                # 3. Adiciona as músicas na playlist nova
                new_pl.add(track_ids)
                print(f"      ✅ Adicionadas {len(track_ids)} faixas.")
            else:
                print("      ⚠️ Playlist vazia, criada apenas a pasta.")
            
            time.sleep(1.0)
        except Exception as e:
            print(f"      ❌ Erro ao copiar playlist: {e}")

    print("\n\n✨ OPERAÇÃO CONCLUÍDA! Verifique sua conta nova (jazaam+tidal2). ✨")

if __name__ == "__main__":
    main()

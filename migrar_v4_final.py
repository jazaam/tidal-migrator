import tidalapi
import sys
import time

DELAY = 0.1 # Rápido, mas seguro

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
    print("=== 🎵 MIGRADOR V4 (SMART: SEM DUPLICATAS + TERCEIROS) 🎵 ===")
    
    # --- LOGIN ---
    print("\n👉 PASSO 1: Logue na CONTA VELHA (Origem)")
    session_old = autenticar("CONTA VELHA (jazaam+tidal1)")
    
    print("\n👉 PASSO 2: Logue na CONTA NOVA (Destino)")
    print("⚠️  Use ABA ANÔNIMA para este link!")
    session_new = autenticar("CONTA NOVA (jazaam+tidal2)")

    user_old = session_old.user
    user_new = session_new.user

    # --- MAPEAMENTO DA CONTA NOVA (PARA EVITAR DUPLICATAS) ---
    print("\n🔍 Analisando o que já existe na conta nova (Para não duplicar)...")
    
    # 1. Pega IDs das músicas que já estão na nova
    current_tracks = user_new.favorites.tracks()
    existing_track_ids = set([t.id for t in current_tracks])
    print(f"   📋 Conta nova já tem {len(existing_track_ids)} músicas.")

    # 2. Pega Nomes das playlists criadas na nova
    current_playlists = user_new.playlists()
    existing_playlist_names = set([p.name for p in current_playlists])
    
    # 3. Pega IDs das playlists de terceiros seguidas na nova
    current_fav_playlists = user_new.favorites.playlists()
    existing_fav_pl_ids = set([p.id for p in current_fav_playlists])

    # --- COMEÇA A MIGRAÇÃO ---

    # 1. TRANSFERIR MÚSICAS (LIKES)
    # Pegamos da velha e INVERTEMOS a lista [::-1] para os mais antigos entrarem primeiro
    old_tracks = user_old.favorites.tracks()
    tracks_to_add = []
    
    # Filtra: Só adiciona na lista se NÃO existir na conta nova
    for track in old_tracks:
        if track.id not in existing_track_ids:
            tracks_to_add.append(track)
    
    # Inverte para manter ordem cronológica de adição
    tracks_ordenadas = tracks_to_add[::-1]
    
    total_new = len(tracks_ordenadas)
    print(f"\n🎵 Músicas novas a transferir: {total_new} (Ignorando as que já existem)")
    
    for i, track in enumerate(tracks_ordenadas):
        try:
            user_new.favorites.add_track(track.id)
            sys.stdout.write(f"\r   Processando: {i+1}/{total_new}")
            sys.stdout.flush()
            time.sleep(DELAY)
        except: pass

    # 2. TRANSFERIR ARTISTAS (Sem duplicar)
    # O Tidal lida bem com add_artist repetido, mas vamos evitar requests inúteis
    print(f"\n\n🎤 Verificando Artistas...")
    old_artists = user_old.favorites.artists()
    new_artists_ids = set([a.id for a in user_new.favorites.artists()])
    
    for artist in old_artists:
        if artist.id not in new_artists_ids:
            try:
                user_new.favorites.add_artist(artist.id)
                sys.stdout.write(".")
                sys.stdout.flush()
                time.sleep(DELAY)
            except: pass

    # 3. PLAYLISTS (O PULO DO GATO PARA TERCEIROS)
    print(f"\n\n📂 Analisando Playlists...")
    old_playlists = user_old.playlists()
    
    for pl in old_playlists:
        try:
            # CASO A: A PLAYLIST É SUA (Creator ID == Você)
            if pl.creator.id == user_old.id:
                # Checa se já existe uma playlist com esse nome na conta nova
                if pl.name in existing_playlist_names:
                    print(f"   ⚠️  Playlist '{pl.name}' já existe. Pulando para não duplicar.")
                else:
                    print(f"   🛠️  Clonando SUA playlist: '{pl.name}'")
                    new_pl = user_new.create_playlist(pl.name, pl.description if pl.description else "")
                    track_ids = [t.id for t in pl.tracks()]
                    if track_ids:
                        new_pl.add(track_ids)
                    time.sleep(1)
            
            # CASO B: A PLAYLIST É DE TERCEIRO (Você só seguia) - ESSA FALTOU ANTES
            else:
                # Checa se você já segue ela na conta nova pelo ID (GUID)
                if pl.id in existing_fav_pl_ids:
                     print(f"   ⏭️  Playlist de terceiro '{pl.name}' já seguida. Pulando.")
                else:
                    print(f"   ❤️  Seguindo playlist de terceiro: '{pl.name}'")
                    # Adiciona a playlist original aos favoritos
                    user_new.favorites.add_playlist(pl.id)
                    time.sleep(0.5)
            
        except Exception as e:
            print(f"   ❌ Erro em '{pl.name}': {e}")

    print("\n\n✨ OPERAÇÃO V4 CONCLUÍDA! ✨")
    print("Nota: As músicas que já existiam na conta nova mantiveram a ordem antiga.")
    print("As músicas que faltavam foram adicionadas agora.")

if __name__ == "__main__":
    main()

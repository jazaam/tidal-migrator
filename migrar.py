import tidalapi
import sys
import time

# Configuração
DELAY = 0.2  # Tempo entre ações para evitar bloqueio

def autenticar(nome):
    print(f"\n🔑 --- LOGIN: {nome} ---")
    session = tidalapi.Session()
    # Inicia o login OAuth2 (Vai gerar o link link.tidal.com)
    session.login_oauth_simple()
    if session.check_login():
        print(f"✅ Logado: {session.user.first_name} (ID: {session.user.id})")
        return session
    else:
        print("❌ Falha no login.")
        sys.exit(1)

def main():
    print("=== 🎵 MIGRADOR TIDAL AUTOMÁTICO 🎵 ===")
    
    # 1. Login na Conta VELHA
    print("\n👉 Passo 1: Logue na conta ANTIGA (Origem)")
    session_old = autenticar("CONTA VELHA")
    
    # 2. Login na Conta NOVA
    print("\n👉 Passo 2: Logue na conta NOVA (Destino)")
    print("⚠️  DICA: Abra o link em aba ANÔNIMA!")
    session_new = autenticar("CONTA NOVA")

    print("\n🔄 Lendo favoritos da conta antiga...")
    user_old = session_old.user
    user_new = session_new.user

    # --- TRACKS (O Cérebro do Algoritmo) ---
    tracks = user_old.favorites.tracks()
    total = len(tracks)
    print(f"\n🎵 Transferindo {total} músicas favoritas...")
    
    for i, track in enumerate(tracks):
        try:
            user_new.favorites.add_track(track.id)
            # Barra de progresso visual
            sys.stdout.write(f"\rProcessando: {i+1}/{total} - {track.name[:20]}...")
            sys.stdout.flush()
            time.sleep(DELAY)
        except Exception:
            pass

    # --- ARTISTAS ---
    artists = user_old.favorites.artists()
    print(f"\n\n🎤 Transferindo {len(artists)} artistas...")
    for artist in artists:
        try:
            user_new.favorites.add_artist(artist.id)
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(DELAY)
        except: pass

    # --- PLAYLISTS ---
    print(f"\n\n📂 Transferindo Playlists...")
    playlists = user_old.playlists()
    for pl in playlists:
        if pl.creator.id == user_old.id: # Só as suas, não as do Tidal
            print(f"   + Criando: {pl.name}")
            new_pl = user_new.create_playlist(pl.name, pl.description)
            track_ids = [t.id for t in pl.tracks()]
            if track_ids:
                new_pl.add(track_ids)
            time.sleep(1)

    print("\n\n✨ SUCESSO! A conta nova já está treinada! ✨")

if __name__ == "__main__":
    main()

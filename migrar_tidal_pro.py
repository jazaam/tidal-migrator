import tidalapi
import sys
import time

# --- CONFIGURAÇÕES ---
DELAY = 0.1
VERSION = "7.0 (Enterprise)"

def print_banner():
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║      TIDAL MIGRATION TOOL - v{VERSION}                ║
    ║  Segurança: Anti-Delete | Anti-Loop | Preserva Versões   ║
    ╚══════════════════════════════════════════════════════════╝
    """)

def autenticar(label):
    print(f"\n🔐 {label}")
    print("------------------------------------------------------------")
    session = tidalapi.Session()
    try:
        session.login_oauth_simple()
    except Exception as e:
        print(f"❌ Erro crítico ao iniciar login: {e}")
        sys.exit(1)
        
    if session.check_login():
        user = session.user
        print(f"✅ CONECTADO: {user.first_name} {user.last_name}")
        print(f"🆔 ID: {user.id}")
        return session
    else:
        print("❌ O tempo limite expirou ou o login falhou.")
        sys.exit(1)

def confirmacao_seguranca(user_old, user_new):
    print("\n\n⚠️  VERIFICAÇÃO DE SEGURANÇA ⚠️")
    print("=" * 50)
    print(f"📤 ORIGEM (Ler):    {user_old.first_name} (ID: {user_old.id})")
    print(f"📥 DESTINO (Gravar): {user_new.first_name} (ID: {user_new.id})")
    print("=" * 50)

    # 1. Trava de Conta Duplicada
    if user_old.id == user_new.id:
        print("\n⛔ ERRO CRÍTICO: As contas de Origem e Destino SÃO IGUAIS!")
        print("Você logou na mesma conta duas vezes. O script foi abortado para sua segurança.")
        sys.exit(1)

    print("\nO script irá COPIAR playlists e favoritos da Origem para o Destino.")
    print("NENHUM DADO SERÁ APAGADO na conta de Origem.")
    
    response = input("\nDigite 'SIM' para começar a migração: ").strip().upper()
    if response != "SIM":
        print("Operação cancelada pelo usuário.")
        sys.exit(0)

def main():
    print_banner()

    try:
        # --- ETAPA 1: LOGIN ---
        session_old = autenticar("PASSO 1: Login na conta de ORIGEM (Velha)")
        print("\n(Abra o próximo link em ABA ANÔNIMA para não misturar as sessões!)\n")
        session_new = autenticar("PASSO 2: Login na conta de DESTINO (Nova)")

        user_old = session_old.user
        user_new = session_new.user

        # --- ETAPA 2: TRAVAS DE SEGURANÇA ---
        confirmacao_seguranca(user_old, user_new)

        # --- ETAPA 3: MAPEAMENTO ---
        print("\n🔍 Escaneando conta destino para evitar duplicatas...")
        existing_track_ids = set([t.id for t in user_new.favorites.tracks()])
        existing_pl_names = set([p.name for p in user_new.playlists() if p.creator.id == user_new.id])
        existing_fav_pl_ids = set([p.id for p in user_new.favorites.playlists()])
        existing_album_ids = set([a.id for a in user_new.favorites.albums()])
        existing_artist_ids = set([a.id for a in user_new.favorites.artists()])

        # --- ETAPA 4: MIGRAÇÃO ---
        
        # 4.1 Tracks
        print(f"\n🎵 Processando Músicas...")
        old_tracks = user_old.favorites.tracks()
        # Filtra e Inverte (Ordem Cronológica)
        tracks_to_add = [t for t in old_tracks if t.id not in existing_track_ids][::-1]
        
        if tracks_to_add:
            print(f"   Adicionando {len(tracks_to_add)} novas músicas...")
            for i, track in enumerate(tracks_to_add):
                try:
                    user_new.favorites.add_track(track.id)
                    sys.stdout.write(f"\r   [{i+1}/{len(tracks_to_add)}] {track.name[:30]}")
                    sys.stdout.flush()
                    time.sleep(DELAY)
                except: pass
        else:
            print("   ✅ Todas as músicas já estão sincronizadas.")

        # 4.2 Álbuns
        print(f"\n\n💿 Processando Álbuns...")
        old_albums = user_old.favorites.albums()
        count = 0
        for album in old_albums:
            if album.id not in existing_album_ids:
                try:
                    user_new.favorites.add_album(album.id)
                    sys.stdout.write(".")
                    sys.stdout.flush()
                    count += 1
                    time.sleep(DELAY)
                except: pass
        print(f" (+{count} álbuns)")

        # 4.3 Artistas
        print(f"\n🎤 Processando Artistas...")
        old_artists = user_old.favorites.artists()
        count = 0
        for artist in old_artists:
            if artist.id not in existing_artist_ids:
                try:
                    user_new.favorites.add_artist(artist.id)
                    count += 1
                    time.sleep(0.05)
                except: pass
        print(f"   Done (+{count} artistas)")

        # 4.4 Playlists (Híbrido)
        print(f"\n📂 Processando Playlists...")
        # Pega criadas e seguidas
        all_playlists = user_old.playlists() + user_old.favorites.playlists()
        # Remove duplicatas
        processed_ids = set()
        
        for pl in all_playlists:
            if pl.id in processed_ids: continue
            processed_ids.add(pl.id)

            try:
                # É PROPRIETÁRIA?
                if pl.creator.id == user_old.id:
                    if pl.name in existing_pl_names:
                        print(f"   ⚠️  '{pl.name}' já existe. Pulando.")
                    else:
                        print(f"   🛠️  Clonando: {pl.name}")
                        new_pl = user_new.create_playlist(pl.name, pl.description or "")
                        track_ids = [t.id for t in pl.tracks()]
                        if track_ids: new_pl.add(track_ids)
                        time.sleep(1)
                
                # É DE TERCEIRO?
                else:
                    if pl.id in existing_fav_pl_ids:
                        print(f"   ⏭️  Já segue: {pl.name}")
                    else:
                        print(f"   ❤️  Seguindo: {pl.name}")
                        user_new.favorites.add_playlist(pl.id)
                        time.sleep(0.5)
            except Exception as e:
                print(f"   ❌ Erro na playlist {pl.name}: {e}")

        print("\n" + "="*60)
        print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*60)

    except KeyboardInterrupt:
        print("\n\n🛑 Script interrompido pelo usuário (Ctrl+C).")
        print("Nenhum dado foi corrompido, apenas a cópia parou.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ocorreu um erro inesperado: {e}")

if __name__ == "__main__":
    main()

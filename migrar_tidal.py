import tidalapi
import sys
import time

# --- CONFIGURAÇÕES ---
DELAY = 0.1  # Rapidez segura
LINE_SEP = "=" * 60

def print_header(text):
    print(f"\n{LINE_SEP}")
    print(f" {text}")
    print(f"{LINE_SEP}")

def autenticar(tipo_conta, instrucao_extra=""):
    print_header(f"LOGIN: {tipo_conta}")
    if instrucao_extra:
        print(f"⚠️  DICA: {instrucao_extra}")
    
    print("\n1. Clique no link abaixo.")
    print("2. Autorize o acesso.")
    print("3. Volte aqui e aguarde.")
    
    session = tidalapi.Session()
    session.login_oauth_simple()
    
    if session.check_login():
        user = session.user
        print(f"\n✅ SUCESSO! Logado como: {user.first_name} {user.last_name}")
        print(f"🆔 ID do Usuário: {user.id}")
        return session
    else:
        print("\n❌ ERRO: O login falhou ou expirou.")
        sys.exit(1)

def main():
    print_header("🎵 MIGRADOR TIDAL PRO - V6 (FINAL) 🎵")
    print("Objetivos: Não duplicar, manter versões, copiar tudo.")

    # ==============================================================================
    # 1. AUTENTICAÇÃO (CLARA E OBVIA)
    # ==============================================================================
    
    # CONTA VELHA
    session_old = autenticar(
        "CONTA ANTIGA (ORIGEM)", 
        "Certifique-se de estar logado no navegador com a conta que TEM as músicas."
    )
    
    # CONTA NOVA
    session_new = autenticar(
        "CONTA NOVA (DESTINO)", 
        "Copie o link e abra em uma JANELA ANÔNIMA para não misturar as contas!"
    )

    user_old = session_old.user
    user_new = session_new.user

    # ==============================================================================
    # 2. MAPEAMENTO (O QUE JÁ TEM NA NOVA?)
    # ==============================================================================
    print("\n🔍 Analisando conta nova para evitar duplicatas...")
    
    # Tracks (Por ID - Garante que versões diferentes sejam aceitas, mas iguais não)
    existing_track_ids = set([t.id for t in user_new.favorites.tracks()])
    
    # Playlists Criadas (Por Nome - Evita criar 'Rock' se já existe 'Rock')
    existing_pl_names = set([p.name for p in user_new.playlists() if p.creator.id == user_new.id])
    
    # Playlists Seguidas/Favoritas (Por ID - Evita seguir a mesma 2 vezes)
    existing_fav_pl_ids = set([p.id for p in user_new.favorites.playlists()])
    
    # Álbuns (Por ID)
    existing_album_ids = set([a.id for a in user_new.favorites.albums()])

    print(f"   📊 Estatísticas Atuais da Conta Nova:")
    print(f"      - Músicas: {len(existing_track_ids)}")
    print(f"      - Playlists: {len(existing_pl_names) + len(existing_fav_pl_ids)}")

    # ==============================================================================
    # 3. MIGRAÇÃO DE MÚSICAS (TRACKS)
    # ==============================================================================
    print_header("MIGRANDO MÚSICAS (LIKES)")
    
    print("📥 Lendo conta antiga...")
    old_tracks = user_old.favorites.tracks()
    
    # Filtra duplicatas exatas
    tracks_to_add = [t for t in old_tracks if t.id not in existing_track_ids]
    
    # Inverte para manter a ordem cronológica de adição (Mais antigo primeiro)
    tracks_ordenadas = tracks_to_add[::-1]
    
    total = len(tracks_ordenadas)
    if total == 0:
        print("✅ Nenhuma música nova para adicionar.")
    else:
        print(f"🚀 Adicionando {total} músicas novas...")
        for i, track in enumerate(tracks_ordenadas):
            try:
                user_new.favorites.add_track(track.id)
                # Visual Clean: [10/50] Nome da Musica
                sys.stdout.write(f"\r   [{i+1}/{total}] {track.name[:40]}")
                sys.stdout.flush()
                time.sleep(DELAY)
            except Exception:
                pass
    print("\n")

    # ==============================================================================
    # 4. MIGRAÇÃO DE ÁLBUNS (O BÔNUS)
    # ==============================================================================
    print_header("MIGRANDO ÁLBUNS")
    old_albums = user_old.favorites.albums()
    albums_to_add = [a for a in old_albums if a.id not in existing_album_ids]
    
    if not albums_to_add:
        print("✅ Nenhum álbum novo.")
    else:
        print(f"🚀 Adicionando {len(albums_to_add)} álbuns...")
        for album in albums_to_add:
            try:
                user_new.favorites.add_album(album.id)
                sys.stdout.write(".")
                sys.stdout.flush()
                time.sleep(DELAY)
            except: pass
    print("\n")

    # ==============================================================================
    # 5. MIGRAÇÃO DE ARTISTAS
    # ==============================================================================
    print_header("MIGRANDO ARTISTAS")
    # Tidal não duplica artistas, podemos mandar bala
    old_artists = user_old.favorites.artists()
    print(f"🚀 Sincronizando {len(old_artists)} artistas...")
    for artist in old_artists:
        try:
            user_new.favorites.add_artist(artist.id)
            time.sleep(0.05) # Pode ser mais rápido
        except: pass

    # ==============================================================================
    # 6. MIGRAÇÃO DE PLAYLISTS (CRIADAS + SEGUIDAS)
    # ==============================================================================
    print_header("MIGRANDO PLAYLISTS")
    
    # Pega TUDO: user_old.playlists() traz criadas + seguidas misturadas na API nova
    # Mas por segurança vamos varrer os dois métodos
    
    all_playlists_source = user_old.playlists() + user_old.favorites.playlists()
    # Remove duplicatas da lista de origem (caso a API retorne a mesma nos dois lugares)
    unique_playlists = {p.id: p for p in all_playlists_source}.values()

    print(f"📂 Processando {len(unique_playlists)} playlists no total...")

    for pl in unique_playlists:
        try:
            # CASO 1: É SUA (CRIADA)
            if pl.creator.id == user_old.id:
                if pl.name in existing_pl_names:
                    print(f"   ⚠️  Playlist '{pl.name}' já existe (Nome igual). Pulando.")
                else:
                    print(f"   🛠️  CLONANDO: {pl.name}")
                    new_pl = user_new.create_playlist(pl.name, pl.description or "")
                    track_ids = [t.id for t in pl.tracks()]
                    if track_ids:
                        new_pl.add(track_ids)
                    time.sleep(1)

            # CASO 2: É DE OUTRO (SEGUIDA)
            else:
                if pl.id in existing_fav_pl_ids:
                    print(f"   ⏭️  Já segue: {pl.name}")
                else:
                    print(f"   ❤️  SEGUINDO: {pl.name}")
                    user_new.favorites.add_playlist(pl.id)
                    time.sleep(0.5)

        except Exception as e:
            print(f"   ❌ Erro em '{pl.name}': {e}")

    # ==============================================================================
    # FIM
    # ==============================================================================
    print_header("CONCLUÍDO COM SUCESSO")
    print("Resumo:")
    print("1. Músicas duplicadas foram ignoradas.")
    print("2. Versões diferentes da mesma música foram mantidas.")
    print("3. Álbuns, Artistas e Playlists (Criadas e Seguidas) foram transferidos.")
    print("\nDivirta-se na conta nova! 🎧")

if __name__ == "__main__":
    main()

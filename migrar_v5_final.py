import tidalapi
import sys
import time

DELAY = 0.2

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
    print("=== 🎵 MIGRADOR V5 (FORÇA BRUTA: CRIADAS + SEGUIDAS) 🎵 ===")
    
    # --- LOGIN ---
    print("\n👉 PASSO 1: Logue na CONTA VELHA (Origem)")
    session_old = autenticar("CONTA VELHA (Ler)")
    
    print("\n👉 PASSO 2: Logue na CONTA NOVA (Destino)")
    print("⚠️  Use ABA ANÔNIMA para este link!")
    session_new = autenticar("CONTA NOVA (Gravar)")

    user_old = session_old.user
    user_new = session_new.user

    # --- LISTAGEM PRÉVIA (SEGURANÇA) ---
    print("\n🔍 Mapeando conta nova para evitar duplicatas...")
    # Mapeia nomes das playlists já criadas na nova
    existing_created_names = set([p.name for p in user_new.playlists()])
    # Mapeia IDs das playlists já seguidas na nova
    existing_followed_ids = set([p.id for p in user_new.favorites.playlists()])

    # ==========================================
    # PARTE 1: PLAYLISTS QUE VOCÊ CRIOU (CREATED)
    # ==========================================
    print("\n\n📂 [1/2] Processando Playlists CRIADAS por você...")
    try:
        created_playlists = user_old.playlists()
        print(f"   Encontradas: {len(created_playlists)}")
        
        for pl in created_playlists:
            # Só migra se você for o dono
            if pl.creator.id == user_old.id:
                if pl.name in existing_created_names:
                    print(f"   ⚠️  Playlist '{pl.name}' já existe na nova. Pulando.")
                else:
                    print(f"   🛠️  Clonando: '{pl.name}'")
                    try:
                        new_pl = user_new.create_playlist(pl.name, pl.description if pl.description else "")
                        track_ids = [t.id for t in pl.tracks()]
                        if track_ids:
                            new_pl.add(track_ids)
                        time.sleep(1)
                    except Exception as e:
                        print(f"      Erro ao criar: {e}")
            else:
                # Se cair aqui, é porque está na lista de criadas mas não é sua (bug do Tidal), tratamos como seguida
                if pl.id not in existing_followed_ids:
                    print(f"   ❤️  Seguindo (detectada como não-proprietária): '{pl.name}'")
                    user_new.favorites.add_playlist(pl.id)
                    time.sleep(0.5)

    except Exception as e:
        print(f"❌ Erro ao ler playlists criadas: {e}")

    # ==========================================
    # PARTE 2: PLAYLISTS QUE VOCÊ SEGUE (FAVORITES)
    # ==========================================
    print("\n\n❤️ [2/2] Processando Playlists SEGUIDAS (De outros)...")
    try:
        fav_playlists = user_old.favorites.playlists()
        print(f"   Encontradas: {len(fav_playlists)}")

        for pl in fav_playlists:
            if pl.id in existing_followed_ids:
                print(f"   ⏭️  Já segue '{pl.name}'. Pulando.")
            else:
                # Verifica se não é uma das suas próprias (para não duplicar lógica)
                if pl.creator.id != user_new.id: 
                    print(f"   ❤️  Seguindo: '{pl.name}'")
                    try:
                        user_new.favorites.add_playlist(pl.id)
                        time.sleep(DELAY)
                    except Exception as e:
                        print(f"      Erro ao seguir: {e}")
    except Exception as e:
        print(f"❌ Erro ao ler playlists favoritas: {e}")

    print("\n\n✨ FIM DA EXECUÇÃO V5 ✨")
    print("Se ainda faltar algo, verifique se as playlists na conta velha estão 'Públicas'.")

if __name__ == "__main__":
    main()

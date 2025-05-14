import os
import re
import datetime
import requests
from bs4 import BeautifulSoup
import psycopg2
from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────────
# Încarcă DSN-ul din .env
# ──────────────────────────────────────────────────────────────
load_dotenv()
DSN = os.getenv("DB_URL")

URL = "https://grkino.com/arhiva.php"

def fetch_last_grkino():
    """
    Extrage ultima tragere completă de pe grkino.com/arhiva.php.
    Întoarce None dacă nu e validă (incompletă sau în viitor).
    """
    resp = requests.get(URL, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Găsește tabela
    table = soup.find("table", id="archive")
    if table is None:
        return None

    # Ultimul rând efectiv de date
    first_tr = table.find_all("tr")[1]
    cols = [td.get_text(strip=True) for td in first_tr.find_all("td")]

    # 1) Parsează data+ora
    try:
        drawn_at = datetime.datetime.strptime(cols[0], "%d.%m.%Y %H:%M")
    except ValueError:
        return None

    # 2) Nu lua tragerile viitoare
    if drawn_at > datetime.datetime.utcnow():
        return None

    # 3) Parsează cele 20 de numere
    nums = [int(n) for n in re.split(r"[,\s\-]+", cols[1]) if n.isdigit()]
    if len(nums) != 20:
        return None

    # 4) ID unic pe baza timestamp-ului UTC
    draw_id = int(drawn_at.replace(tzinfo=datetime.timezone.utc).timestamp())

    return {"id": draw_id, "drawn_at": drawn_at, "nums": nums}

def main():
    # 1) Extrage ultima tragere
    last = fetch_last_grkino()
    if last is None:
        print("Nicio extragere validă găsită. Skip.")
        return

    # 2) Inserează în Supabase (ignori duplicatele)
    with psycopg2.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.kino_draws (id, drawn_at, nums)
                VALUES (%(id)s, %(drawn_at)s, %(nums)s)
                ON CONFLICT (id) DO NOTHING;
            """, last)
        conn.commit()

    print("Ultima tragere importată:", last)

if __name__ == "__main__":
    main()
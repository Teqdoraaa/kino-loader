import os
import re
import datetime
import requests
from bs4 import BeautifulSoup
import psycopg2
from dotenv import load_dotenv

# Încarcă DSN-ul din .env
load_dotenv()
DSN = os.getenv("DB_URL")

# URL-ul paginii cu arhiva Kino Grecia
URL = "https://grkino.com/arhiva.php"

def fetch_history_grkino():
    """
    Generează toate tragerile istorice complete de pe grkino.com/arhiva.php.
    Ignoră intrările care nu au exact 20 de numere sau care sunt programate în viitor.
    Returnează un generator de dict-uri cu 'drawn_at' (datetime) și 'nums' (list[int]).
    """
    resp = requests.get(URL, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", id="archive")
    if table is None:
        raise RuntimeError("Nu am găsit tabelul #archive pe pagina grkino.com")

    now = datetime.datetime.utcnow()
    for tr in table.find_all("tr")[1:]:  # sărim header-ul
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        # coloana 0: data și ora "DD.MM.YYYY HH:MM"
        try:
            drawn_at = datetime.datetime.strptime(cols[0], "%d.%m.%Y %H:%M")
        except Exception:
            continue

        # nu prelucra tragerile viitoare
        if drawn_at > now:
            continue

        # coloana 1: string cu numere separate prin spațiu sau virgulă
        nums = [int(n) for n in re.split(r"[,\s\-]+", cols[1]) if n.isdigit()]

        # filtrăm doar cele cu exact 20 de numere
        if len(nums) != 20:
            continue

        yield {"drawn_at": drawn_at, "nums": nums}

def fetch_last_grkino():
    """
    Extrage ultima tragere completă de pe grkino.com/arhiva.php.
    Întoarce None dacă nu e validă (viitoare sau incompletă).
    Returnează dict cu 'id', 'drawn_at' și 'nums'.
    """
    resp = requests.get(URL, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", id="archive")
    if table is None:
        raise RuntimeError("Nu am găsit tabelul #archive pe pagina grkino.com")

    now = datetime.datetime.utcnow()
    first_tr = table.find_all("tr")[1]
    cols = [td.get_text(strip=True) for td in first_tr.find_all("td")]

    try:
        drawn_at = datetime.datetime.strptime(cols[0], "%d.%m.%Y %H:%M")
    except Exception:
        return None

    # nu prelucra dacă e în viitor
    if drawn_at > now:
        return None

    nums = [int(n) for n in re.split(r"[,\s\-]+", cols[1]) if n.isdigit()]
    if len(nums) != 20:
        return None

    # ID = timestamp-ul UTC
    draw_id = int(drawn_at.replace(tzinfo=datetime.timezone.utc).timestamp())
    return {"id": draw_id, "drawn_at": drawn_at, "nums": nums}

def main():
    # 1) Bulk-import istoric (doar o dată, pe rerun ignoră duplicatele)
    with psycopg2.connect(DSN) as conn:
        with conn.cursor() as cur:
            for rec in fetch_history_grkino():
                cur.execute("""
                    INSERT INTO public.kino_draws (drawn_at, nums)
                    VALUES (%s, %s)
                    ON CONFLICT (drawn_at) DO NOTHING;
                """, (rec["drawn_at"], rec["nums"]))
        conn.commit()
    print("Istoric importat.")

    # 2) Import periodic al ultimei extrageri
    last = fetch_last_grkino()
    if last is None:
        print("Nicio extragere validă găsită (skip incompletă sau viitoare).")
        return

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
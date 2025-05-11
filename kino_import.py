import os
import datetime
import requests
from bs4 import BeautifulSoup
import psycopg2
from dotenv import load_dotenv

# Încarcă DSN-ul din .env (pooler + sslmode/gssencmode)
load_dotenv()
DSN = os.getenv("DB_URL")

URL = "https://grkino.com/arhiva.php"

def fetch_today_draws():
    """
    Yield dict-uri {'id', 'drawn_at', 'nums'} pentru tragerile din ziua curentă.
    Se caută fiecare apariție a textului "Extragere", apoi următoarea linie
    e timestamp-ul, iar următoarele linii sunt numere (un număr per linie).
    """
    resp = requests.get(URL, timeout=10)
    resp.raise_for_status()

    # Extragem tot textul paginii, păstrăm liniile nenule
    text = BeautifulSoup(resp.text, "html.parser").get_text(separator="\n")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    today = datetime.date.today()

    for i, line in enumerate(lines):
        if line != "Extragere":
            continue
        # linia următoare ar trebui să fie timestamp-ul
        if i+1 >= len(lines):
            continue
        ts = lines[i+1]  # ex: "15:05:00 10.05.2025"
        try:
            dt = datetime.datetime.strptime(ts, "%H:%M:%S %d.%m.%Y")
        except ValueError:
            continue
        if dt.date() != today:
            continue

        # colecția de numere începe de la i+2
        nums = []
        j = i+2
        while j < len(lines) and lines[j].isdigit():
            nums.append(int(lines[j]))
            j += 1
        if not nums:
            continue

        draw_id = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
        yield {"id": draw_id, "drawn_at": dt, "nums": nums}

def main():
    today = datetime.date.today()
    draws = list(fetch_today_draws())
    if not draws:
        print("Nu sunt extrageri pentru azi.")
        return

    # Inserăm în baza de date
    with psycopg2.connect(DSN) as conn:
        with conn.cursor() as cur:
            for rec in draws:
                cur.execute("""
                    INSERT INTO public.kino_draws (id, drawn_at, nums)
                    VALUES (%(id)s, %(drawn_at)s, %(nums)s)
                    ON CONFLICT (id) DO NOTHING;
                """, rec)
        conn.commit()

    print(f"S-au importat {len(draws)} extrageri pentru {today.isoformat()}:")
    for rec in draws:
        print(f"  • {rec['drawn_at'].strftime('%H:%M:%S')} → {rec['nums']}")

if __name__ == "__main__":
    main()
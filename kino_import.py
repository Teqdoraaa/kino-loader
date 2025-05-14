def fetch_last_grkino():
    """
    Extrage ultima tragere completă de pe grkino.com/arhiva.php.
    Întoarce None dacă nu e validă (incompletă sau în viitor).
    """
    resp = requests.get(URL, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Debug: listăm tabelele de pe pagină
    tables = soup.find_all("table")
    print(f"[DEBUG] Găsite {len(tables)} tabele pe pagină")
    for i, t in enumerate(tables):
        print(f"[DEBUG] Tabel {i}: {len(t.find_all('tr'))} rânduri, attrs={t.attrs}")

    # Alege primul tabel care are cel puțin 2 rânduri:
    table = None
    for t in tables:
        if len(t.find_all("tr")) >= 2:
            table = t
            break
    if table is None:
        print("Nu am găsit niciun tabel util cu trageri.")
        return None

    # Luăm al doilea <tr> (primul după header)
    rows = table.find_all("tr")
    first_tr = rows[1]
    cols = [td.get_text(strip=True) for td in first_tr.find_all("td")]

    # parse date+ora
    try:
        drawn_at = datetime.datetime.strptime(cols[0], "%d.%m.%Y %H:%M")
    except Exception:
        print(f"[DEBUG] Nu am putut parsa data din '{cols[0]}'")
        return None

    # filtrăm viitorul
    now = datetime.datetime.utcnow()
    if drawn_at > now:
        print(f"[DEBUG] Extragere viitoare ({drawn_at}), skip.")
        return None

    # extragem numerele
    nums = [int(n) for n in re.split(r"[,\s\-]+", cols[1]) if n.isdigit()]
    if len(nums) != 20:
        print(f"[DEBUG] Numere neterminate ({len(nums)} în loc de 20), skip.")
        return None

    draw_id = int(drawn_at.replace(tzinfo=datetime.timezone.utc).timestamp())
    return {"id": draw_id, "drawn_at": drawn_at, "nums": nums}
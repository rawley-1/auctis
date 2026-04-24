import requests
from pathlib import Path

BASE_DIR = Path(__file__).parent
OPINIONS_DIR = BASE_DIR / "opinions"

OPINIONS_DIR.mkdir(exist_ok=True)

cases = {
    "revlon": "https://www.courtlistener.com/opinion/2418092/revlon-inc-v-macandrews-forbes-holdings-inc/?format=txt",
    "unocal": "https://www.courtlistener.com/opinion/2418183/unocal-corp-v-mesa-petroleum-co/?format=txt",
    "caremark": "https://www.courtlistener.com/opinion/2416996/in-re-caremark-international-inc-derivative-litigation/?format=txt",
}

def download_case(name, url):
    print(f"Downloading {name}...")

    r = requests.get(url)

    if r.status_code == 200:
        path = OPINIONS_DIR / f"{name}.txt"
        path.write_text(r.text)
        print(f"Saved {name}")
    else:
        print(f"Failed: {name} ({r.status_code})")

def main():
    for name, url in cases.items():
        download_case(name, url)

if __name__ == "__main__":
    main()

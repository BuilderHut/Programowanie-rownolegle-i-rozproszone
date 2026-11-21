# Programowanie rownolegle i rozproszone - Temat 3

Kompletny projekt realizujacy:

1. rownolegle przetwarzanie obrazu w Pythonie przy uzyciu `multiprocessing.Pool`,
2. rozproszone przetwarzanie obrazu przez serwer i wielu klientow TCP.

Oba zadania wykorzystuja wlasna implementacje filtru Sobela oparta wyłącznie na NumPy.
Obraz jest dzielony na poziome fragmenty z jednopikselowym marginesem. Margines daje
filtrowi dostep do sasiedniego wiersza, dlatego po scaleniu nie ma sztucznych krawedzi
w miejscach podzialu.

## Wymagania

- Python 3.10 lub nowszy,
- pakiety z `requirements.txt`,
- w zadaniu 2 komputery musza znajdowac sie w tej samej sieci i miec dostep do
  wybranego portu TCP (domyslnie 2040).

Instalacja:

```powershell
python -m pip install -r requirements.txt
```

Przykladowy obraz mozna wygenerowac poleceniem:

```powershell
python generate_sample.py
```

## Zadanie 1 - wiele procesow

```powershell
python task1_parallel.py sample_input.png --workers 4 --benchmark
```

Wynik zostanie zapisany jako `processed_parallel.png`. Opcja `--benchmark`
porownuje wynik z wykonaniem sekwencyjnym i potwierdza, ze oba obrazy sa identyczne.
Dla malego obrazu narzut uruchomienia procesow moze byc wiekszy od zysku; roznica jest
lepiej widoczna dla duzych obrazow lub bardziej kosztownych filtrow.

## Zadanie 2 - test lokalny

Najprostszy test uruchamia serwer i dwa klienty na jednym komputerze:

```powershell
python local_demo.py sample_input.png --clients 2
```

Wynik zostanie zapisany jako `processed_distributed.png`.

## Zadanie 2 - kilka komputerow

1. Na komputerze serwera sprawdz jego adres IPv4 poleceniem `ipconfig`.
2. Uruchom serwer, podajac liczbe klientow:

```powershell
python server.py sample_input.png --host 0.0.0.0 --port 2040 --clients 2
```

3. Na kazdym z dwoch komputerow klienckich skopiuj pliki projektu, zainstaluj
   zaleznosci i uruchom klienta. Zastap `192.168.1.3` rzeczywistym adresem serwera:

```powershell
python client.py --host 192.168.1.3 --port 2040
```

Kazdy klient odbiera jeden fragment, stosuje filtr i odsyla wynik. Serwer obsluguje
klientow rownolegle, weryfikuje indeksy oraz wymiary odpowiedzi, scala fragmenty i
zapisuje gotowy obraz.

Jesli klient nie moze sie polaczyc, nalezy sprawdzic:

- czy serwer zostal uruchomiony przed klientami,
- czy adres IPv4 i port sa poprawne,
- czy zapora Windows zezwala Pythonowi na polaczenia w sieci prywatnej,
- czy komputery sa w tej samej sieci lokalnej.

## Testy

```powershell
python -m unittest discover -v
```

Testy sprawdzaja filtr Sobela, poprawne dzielenie i scalanie, ramkowanie wiadomosci
TCP oraz pelny przeplyw serwer - dwoch klientow - obraz wynikowy.

## Pliki projektu

- `image_processing.py` - filtr Sobela, dzielenie, przetwarzanie i scalanie,
- `task1_parallel.py` - program zadania 1,
- `network_protocol.py` - funkcje `send_all` i `receive_all`,
- `server.py` - serwer zadania 2,
- `client.py` - klient zadania 2,
- `local_demo.py` - automatyczna demonstracja na jednym komputerze,
- `generate_sample.py` - generator obrazu testowego,
- `tests/` - testy jednostkowe i integracyjny.

## Uwaga o bezpieczenstwie

Zgodnie z materialem do laboratorium komunikaty sa serializowane przez `pickle`.
Takiego protokolu nalezy uzywac tylko miedzy zaufanymi komputerami w sieci
laboratoryjnej. Nie nalezy wystawiac serwera do Internetu.

# Temat 4 - zadanie 1

Rozwiązanie implementuje równoległy algorytm genetyczny dla dyskretnego problemu
szeregowania **permutation flow shop (PFSP)**. Każde zadanie przechodzi przez te same
maszyny w tej samej kolejności, a chromosom określa kolejność zadań. Minimalizowana
jest długość całego harmonogramu `Cmax` (makespan).

## Dlaczego rozwiązanie spełnia wymagania

- istnieje jedna wspólna populacja i wspólne pokolenia algorytmu;
- ocena populacji początkowej jest rozdzielana między procesy;
- w każdym pokoleniu procesy równolegle wykonują krzyżowanie OX, mutację przez zamianę
  dwóch genów oraz ocenę potomków;
- selekcja turniejowa i elitaryzm scalają wyniki w następne wspólne pokolenie;
- nie jest to zabroniony `multi-start` - procesy nie uruchamiają niezależnych algorytmów.

Kod używa tylko biblioteki standardowej Pythona. `ProcessPoolExecutor` uruchamia osobne
procesy, dzięki czemu obliczenia CPU nie są ograniczone przez GIL.

## Uruchomienie

Wymagany jest Python 3.10 lub nowszy. W PowerShell, z katalogu projektu:

```powershell
python .\parallel_ga.py
```

Przykład z własnymi parametrami i zapisem historii pokoleń:

```powershell
python .\parallel_ga.py `
  --workers 4 `
  --population-size 200 `
  --generations 300 `
  --history-csv .\results\history.csv
```

Najważniejsze opcje można wyświetlić poleceniem:

```powershell
python .\parallel_ga.py --help
```

Tryb `--workers 1` jest wersją referencyjną do testów poprawności i późniejszego
porównania czasów. Właściwe rozwiązanie równoległe należy uruchamiać z wartością większą
od 1. Dla małych instancji koszt komunikacji między procesami może być większy niż zysk
czasowy; analizę skalowania można wykonać w zadaniu 3.

## Format danych

Domyślnie program używa `data/example_pfsp.json`. Każdy wiersz macierzy opisuje jedno
zadanie, a kolejne liczby są czasami wykonania tego zadania na maszynach 1, 2, ...

```json
{
  "name": "moja-instancja",
  "processing_times": [
    [2, 3, 4],
    [1, 4, 2],
    [3, 2, 5]
  ]
}
```

Własny plik wybiera się przez `--input`:

```powershell
python .\parallel_ga.py --input .\data\moja_instancja.json --workers 4
```

## Testy

```powershell
python -m unittest discover -s tests -v
```

Testy sprawdzają funkcję celu, poprawność operatorów genetycznych, elitaryzm oraz
identyczność wyniku dla jednego i wielu procesów przy tym samym ziarnie losowym.

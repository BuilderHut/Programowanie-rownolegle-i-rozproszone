# Temat 1 - zadanie 1

Program symuluje równoległe wydobycie i transport 2000 jednostek węgla. Korzysta z klasy
`Task` oraz semaforów `SemaphoreSlim`:

- przy złożu mogą jednocześnie pracować maksymalnie 2 osoby,
- w magazynie może jednocześnie rozładowywać się 1 pojazd,
- pojazd mieści 200 jednostek węgla,
- wydobycie i rozładunek jednej jednostki trwają po 10 ms,
- transport do magazynu trwa 10 s.

Domyślnie program uruchamia pięciu górników:

```powershell
dotnet run
```

Inną liczbę górników można przekazać jako argument, na przykład:

```powershell
dotnet run -- 3
```

Po zakończeniu program sprawdza stan złoża i magazynu oraz wypisuje całkowity czas symulacji.

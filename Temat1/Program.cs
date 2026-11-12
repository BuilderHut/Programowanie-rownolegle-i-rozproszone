using System.Diagnostics;
using System.Text;

internal static class Program
{
    private const int PoczatkowyStanZloza = 2_000;
    private const int PojemnoscPojazdu = 200;
    private const int CzasWydobyciaJednostkiMs = 10;
    private const int CzasRozladunkuJednostkiMs = 10;
    private const int CzasTransportuMs = 10_000;
    private const int DomyslnaLiczbaGornikow = 5;

    // Przy złożu mogą jednocześnie pracować dwaj górnicy.
    private static readonly SemaphoreSlim SemaforZloza = new(2, 2);

    // W magazynie może jednocześnie rozładowywać się jeden pojazd.
    private static readonly SemaphoreSlim SemaforMagazynu = new(1, 1);

    private static readonly object BlokadaZloza = new();
    private static readonly object BlokadaMagazynu = new();
    private static readonly object BlokadaKonsoli = new();

    private static int stanZloza = PoczatkowyStanZloza;
    private static int stanMagazynu;

    private static async Task Main(string[] argumenty)
    {
        Console.OutputEncoding = Encoding.UTF8;

        if (!SprobujPobracLiczbeGornikow(argumenty, out int liczbaGornikow))
        {
            Console.WriteLine("Użycie: dotnet run -- [liczba_górników]");
            Console.WriteLine("Liczba górników musi być dodatnią liczbą całkowitą.");
            return;
        }

        Console.WriteLine("=== Symulacja kopalni ===");
        Console.WriteLine($"Liczba górników: {liczbaGornikow}");
        Console.WriteLine($"Stan początkowy złoża: {PoczatkowyStanZloza} jednostek węgla");
        Console.WriteLine();

        Stopwatch stoper = Stopwatch.StartNew();

        Task[] zadaniaGornikow = Enumerable.Range(1, liczbaGornikow)
            .Select(numerGornika => Task.Run(() => GornikAsync(numerGornika)))
            .ToArray();

        await Task.WhenAll(zadaniaGornikow);
        stoper.Stop();

        Console.WriteLine();
        Console.WriteLine("=== Koniec symulacji ===");
        Console.WriteLine($"Pozostało w złożu: {PobierzStanZloza()} jednostek węgla");
        Console.WriteLine($"Stan magazynu: {PobierzStanMagazynu()} jednostek węgla");
        Console.WriteLine($"Czas symulacji: {stoper.Elapsed.TotalSeconds:F2} s");
    }

    private static async Task GornikAsync(int numerGornika)
    {
        while (true)
        {
            int zaladowanyWegiel = await ZaladujPojazdAsync(numerGornika);

            if (zaladowanyWegiel == 0)
            {
                ZapiszLog($"Górnik {numerGornika} zakończył pracę.");
                return;
            }

            ZapiszLog($"Górnik {numerGornika} transportuje {zaladowanyWegiel} jednostek węgla do magazynu...");
            await Task.Delay(CzasTransportuMs);

            await RozladujPojazdAsync(numerGornika, zaladowanyWegiel);
        }
    }

    private static async Task<int> ZaladujPojazdAsync(int numerGornika)
    {
        await SemaforZloza.WaitAsync();

        try
        {
            if (PobierzStanZloza() == 0)
            {
                return 0;
            }

            ZapiszLog($"Górnik {numerGornika} rozpoczyna wydobycie...");

            int zaladowanyWegiel = 0;

            while (zaladowanyWegiel < PojemnoscPojazdu)
            {
                bool wydobytoWegiel;

                lock (BlokadaZloza)
                {
                    wydobytoWegiel = stanZloza > 0;

                    if (wydobytoWegiel)
                    {
                        stanZloza--;
                        zaladowanyWegiel++;
                    }
                }

                if (!wydobytoWegiel)
                {
                    break;
                }

                await Task.Delay(CzasWydobyciaJednostkiMs);
            }

            lock (BlokadaZloza)
            {
                ZapiszLog(
                    $"Górnik {numerGornika} wydobył {zaladowanyWegiel} jednostek węgla. " +
                    $"Pozostało w złożu: {stanZloza} jednostek.");
            }

            return zaladowanyWegiel;
        }
        finally
        {
            SemaforZloza.Release();
        }
    }

    private static async Task RozladujPojazdAsync(int numerGornika, int zaladowanyWegiel)
    {
        await SemaforMagazynu.WaitAsync();

        try
        {
            ZapiszLog($"Górnik {numerGornika} rozładowuje węgiel...");

            for (int numerJednostki = 0; numerJednostki < zaladowanyWegiel; numerJednostki++)
            {
                await Task.Delay(CzasRozladunkuJednostkiMs);

                lock (BlokadaMagazynu)
                {
                    stanMagazynu++;
                }
            }

            ZapiszLog(
                $"Górnik {numerGornika} zakończył rozładunek. " +
                $"Stan magazynu: {PobierzStanMagazynu()} jednostek.");
        }
        finally
        {
            SemaforMagazynu.Release();
        }
    }

    private static int PobierzStanZloza()
    {
        lock (BlokadaZloza)
        {
            return stanZloza;
        }
    }

    private static int PobierzStanMagazynu()
    {
        lock (BlokadaMagazynu)
        {
            return stanMagazynu;
        }
    }

    private static void ZapiszLog(string komunikat)
    {
        lock (BlokadaKonsoli)
        {
            Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] {komunikat}");
        }
    }

    private static bool SprobujPobracLiczbeGornikow(string[] argumenty, out int liczbaGornikow)
    {
        liczbaGornikow = 0;

        if (argumenty.Length == 0)
        {
            liczbaGornikow = DomyslnaLiczbaGornikow;
            return true;
        }

        return argumenty.Length == 1
            && int.TryParse(argumenty[0], out liczbaGornikow)
            && liczbaGornikow > 0;
    }
}

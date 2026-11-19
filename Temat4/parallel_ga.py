"""Rownolegly algorytm genetyczny dla permutation flow shop scheduling.

Chromosom jest permutacja zadan. Operacje tworzenia potomstwa (krzyzowanie,
mutacja i ocena) sa wykonywane rownolegle we wspolnej puli procesow. Nie jest
to multi-start: wszystkie procesy pracuja na jednej populacji i wspolnych
pokoleniach algorytmu genetycznego.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence, TypeVar


Permutation = tuple[int, ...]
ProcessingTimes = tuple[tuple[int, ...], ...]
T = TypeVar("T")
R = TypeVar("R")

_WORKER_PROCESSING_TIMES: ProcessingTimes | None = None


@dataclass(frozen=True)
class FlowShopInstance:
    name: str
    processing_times: ProcessingTimes

    @property
    def jobs(self) -> int:
        return len(self.processing_times)

    @property
    def machines(self) -> int:
        return len(self.processing_times[0])


@dataclass(frozen=True)
class GAConfig:
    population_size: int = 120
    generations: int = 150
    crossover_rate: float = 0.90
    mutation_rate: float = 0.12
    tournament_size: int = 4
    elite_count: int = 2
    workers: int = 1
    seed: int = 2026


@dataclass(frozen=True)
class Individual:
    permutation: Permutation
    makespan: int


@dataclass(frozen=True)
class GenerationStats:
    generation: int
    best_makespan: int
    average_makespan: float


@dataclass(frozen=True)
class GAResult:
    best: Individual
    history: tuple[GenerationStats, ...]
    elapsed_seconds: float


ProgressCallback = Callable[[GenerationStats], None]
OffspringPayload = tuple[Permutation, Permutation, float, float, int]


def validate_instance(instance: FlowShopInstance) -> None:
    if len(instance.processing_times) < 2:
        raise ValueError("Instancja musi zawierac co najmniej dwa zadania.")

    machine_count = len(instance.processing_times[0])
    if machine_count < 2:
        raise ValueError("Instancja musi zawierac co najmniej dwie maszyny.")

    for job_index, row in enumerate(instance.processing_times):
        if len(row) != machine_count:
            raise ValueError(
                f"Zadanie {job_index + 1} ma inna liczbe czasow niz pozostale."
            )
        if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in row):
            raise ValueError(
                f"Czasy zadania {job_index + 1} musza byc dodatnimi liczbami calkowitymi."
            )


def validate_config(config: GAConfig) -> None:
    if config.population_size < 4:
        raise ValueError("Rozmiar populacji musi wynosic co najmniej 4.")
    if config.generations < 1:
        raise ValueError("Liczba pokolen musi wynosic co najmniej 1.")
    if not 0.0 <= config.crossover_rate <= 1.0:
        raise ValueError("Prawdopodobienstwo krzyzowania musi nalezec do [0, 1].")
    if not 0.0 <= config.mutation_rate <= 1.0:
        raise ValueError("Prawdopodobienstwo mutacji musi nalezec do [0, 1].")
    if not 2 <= config.tournament_size <= config.population_size:
        raise ValueError("Rozmiar turnieju musi nalezec do [2, rozmiar populacji].")
    if not 1 <= config.elite_count < config.population_size:
        raise ValueError("Liczba elit musi nalezec do [1, rozmiar populacji - 1].")
    if config.workers < 1:
        raise ValueError("Liczba procesow musi wynosic co najmniej 1.")


def load_instance(path: str | Path) -> FlowShopInstance:
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)

    if not isinstance(data, dict):
        raise ValueError("Plik instancji musi zawierac obiekt JSON.")

    name = data.get("name", input_path.stem)
    rows = data.get("processing_times")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Pole 'name' musi byc niepustym napisem.")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Pole 'processing_times' musi byc niepusta tablica.")

    try:
        processing_times = tuple(tuple(row) for row in rows)
    except TypeError as exc:
        raise ValueError("Kazdy wiersz 'processing_times' musi byc tablica.") from exc

    instance = FlowShopInstance(name=name.strip(), processing_times=processing_times)
    validate_instance(instance)
    return instance


def calculate_makespan(
    permutation: Sequence[int], processing_times: ProcessingTimes
) -> int:
    """Oblicz czas zakonczenia wszystkich zadan na ostatniej maszynie."""
    machine_count = len(processing_times[0])
    completion = [0] * machine_count

    for job in permutation:
        completion[0] += processing_times[job][0]
        for machine in range(1, machine_count):
            completion[machine] = (
                max(completion[machine], completion[machine - 1])
                + processing_times[job][machine]
            )

    return completion[-1]


def order_crossover(
    parent_a: Permutation, parent_b: Permutation, rng: random.Random
) -> Permutation:
    """Operator OX zachowujacy dopuszczalna permutacje zadan."""
    size = len(parent_a)
    left, right = sorted(rng.sample(range(size), 2))
    child = [-1] * size
    child[left : right + 1] = parent_a[left : right + 1]

    inherited = set(parent_a[left : right + 1])
    donor_order = parent_b[right + 1 :] + parent_b[: right + 1]
    remaining = [gene for gene in donor_order if gene not in inherited]
    open_positions = list(range(right + 1, size)) + list(range(0, left))

    for position, gene in zip(open_positions, remaining, strict=True):
        child[position] = gene

    return tuple(child)


def swap_mutation(
    permutation: Permutation, mutation_rate: float, rng: random.Random
) -> Permutation:
    if rng.random() >= mutation_rate:
        return permutation

    first, second = rng.sample(range(len(permutation)), 2)
    mutated = list(permutation)
    mutated[first], mutated[second] = mutated[second], mutated[first]
    return tuple(mutated)


def _init_worker(processing_times: ProcessingTimes) -> None:
    global _WORKER_PROCESSING_TIMES
    _WORKER_PROCESSING_TIMES = processing_times


def _worker_times() -> ProcessingTimes:
    if _WORKER_PROCESSING_TIMES is None:
        raise RuntimeError("Proces roboczy nie otrzymal danych instancji.")
    return _WORKER_PROCESSING_TIMES


def _evaluate_worker(permutation: Permutation) -> Individual:
    return Individual(
        permutation=permutation,
        makespan=calculate_makespan(permutation, _worker_times()),
    )


def _offspring_worker(payload: OffspringPayload) -> tuple[Individual, Individual]:
    parent_a, parent_b, crossover_rate, mutation_rate, seed = payload
    rng = random.Random(seed)

    if rng.random() < crossover_rate:
        child_a = order_crossover(parent_a, parent_b, rng)
        child_b = order_crossover(parent_b, parent_a, rng)
    else:
        child_a, child_b = parent_a, parent_b

    child_a = swap_mutation(child_a, mutation_rate, rng)
    child_b = swap_mutation(child_b, mutation_rate, rng)
    processing_times = _worker_times()

    return (
        Individual(child_a, calculate_makespan(child_a, processing_times)),
        Individual(child_b, calculate_makespan(child_b, processing_times)),
    )


def _parallel_map(
    executor: ProcessPoolExecutor | None,
    function: Callable[[T], R],
    values: Sequence[T],
    workers: int,
) -> list[R]:
    if executor is None:
        return [function(value) for value in values]

    chunk_size = max(1, len(values) // (workers * 4))
    return list(executor.map(function, values, chunksize=chunk_size))


def _initial_permutations(
    instance: FlowShopInstance, population_size: int, rng: random.Random
) -> list[Permutation]:
    jobs = tuple(range(instance.jobs))
    # Pierwszy osobnik jest prosta heurystyka: zadania od najwiekszego lacznego czasu.
    heuristic = tuple(
        sorted(jobs, key=lambda job: sum(instance.processing_times[job]), reverse=True)
    )
    population = [heuristic]
    population.extend(tuple(rng.sample(jobs, len(jobs))) for _ in range(population_size - 1))
    return population


def _tournament_index(
    population: Sequence[Individual],
    tournament_size: int,
    rng: random.Random,
    excluded_index: int | None = None,
) -> int:
    candidates = [
        index for index in range(len(population)) if index != excluded_index
    ]
    sample_size = min(tournament_size, len(candidates))
    contenders = rng.sample(candidates, sample_size)
    return min(contenders, key=lambda index: population[index].makespan)


def _statistics(generation: int, population: Sequence[Individual]) -> GenerationStats:
    best = min(individual.makespan for individual in population)
    average = sum(individual.makespan for individual in population) / len(population)
    return GenerationStats(generation, best, average)


def _run_ga_loop(
    instance: FlowShopInstance,
    config: GAConfig,
    executor: ProcessPoolExecutor | None,
    progress_callback: ProgressCallback | None,
) -> tuple[Individual, tuple[GenerationStats, ...]]:
    rng = random.Random(config.seed)
    permutations = _initial_permutations(instance, config.population_size, rng)
    population = _parallel_map(
        executor, _evaluate_worker, permutations, config.workers
    )

    history = [_statistics(0, population)]
    if progress_callback is not None:
        progress_callback(history[-1])

    for generation in range(1, config.generations + 1):
        ranked = sorted(population, key=lambda individual: individual.makespan)
        elites = ranked[: config.elite_count]
        offspring_needed = config.population_size - len(elites)
        pair_count = math.ceil(offspring_needed / 2)
        payloads: list[OffspringPayload] = []

        for _ in range(pair_count):
            first_index = _tournament_index(
                population, config.tournament_size, rng
            )
            second_index = _tournament_index(
                population,
                config.tournament_size,
                rng,
                excluded_index=first_index,
            )
            payloads.append(
                (
                    population[first_index].permutation,
                    population[second_index].permutation,
                    config.crossover_rate,
                    config.mutation_rate,
                    rng.getrandbits(64),
                )
            )

        pairs = _parallel_map(executor, _offspring_worker, payloads, config.workers)
        offspring = [child for pair in pairs for child in pair]
        population = elites + offspring[:offspring_needed]

        stats = _statistics(generation, population)
        history.append(stats)
        if progress_callback is not None:
            progress_callback(stats)

    return min(population, key=lambda individual: individual.makespan), tuple(history)


def run_genetic_algorithm(
    instance: FlowShopInstance,
    config: GAConfig,
    progress_callback: ProgressCallback | None = None,
) -> GAResult:
    validate_instance(instance)
    validate_config(config)
    started = time.perf_counter()

    if config.workers == 1:
        _init_worker(instance.processing_times)
        best, history = _run_ga_loop(
            instance, config, executor=None, progress_callback=progress_callback
        )
    else:
        with ProcessPoolExecutor(
            max_workers=config.workers,
            initializer=_init_worker,
            initargs=(instance.processing_times,),
        ) as executor:
            best, history = _run_ga_loop(
                instance, config, executor, progress_callback
            )

    return GAResult(
        best=best,
        history=history,
        elapsed_seconds=time.perf_counter() - started,
    )


def save_history(path: str | Path, history: Iterable[GenerationStats]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("generation", "best_makespan", "average_makespan"))
        for stats in history:
            writer.writerow(
                (stats.generation, stats.best_makespan, f"{stats.average_makespan:.3f}")
            )


def _default_workers() -> int:
    return max(1, min(8, (os.cpu_count() or 2) - 1))


def build_argument_parser() -> argparse.ArgumentParser:
    default_input = Path(__file__).resolve().parent / "data" / "example_pfsp.json"
    parser = argparse.ArgumentParser(
        description=(
            "Rownolegly algorytm genetyczny dla problemu permutation flow shop."
        )
    )
    parser.add_argument("--input", type=Path, default=default_input)
    parser.add_argument("--population-size", type=int, default=120)
    parser.add_argument("--generations", type=int, default=150)
    parser.add_argument("--crossover-rate", type=float, default=0.90)
    parser.add_argument("--mutation-rate", type=float, default=0.12)
    parser.add_argument("--tournament-size", type=int, default=4)
    parser.add_argument("--elite-count", type=int, default=2)
    parser.add_argument("--workers", type=int, default=_default_workers())
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--history-csv", type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    if args.log_every < 1:
        parser.error("--log-every musi wynosic co najmniej 1")

    try:
        instance = load_instance(args.input)
        config = GAConfig(
            population_size=args.population_size,
            generations=args.generations,
            crossover_rate=args.crossover_rate,
            mutation_rate=args.mutation_rate,
            tournament_size=args.tournament_size,
            elite_count=args.elite_count,
            workers=args.workers,
            seed=args.seed,
        )
        validate_config(config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    def report_progress(stats: GenerationStats) -> None:
        if (
            stats.generation == 0
            or stats.generation == config.generations
            or stats.generation % args.log_every == 0
        ):
            print(
                f"Pokolenie {stats.generation:4d}: "
                f"najlepszy Cmax={stats.best_makespan}, "
                f"sredni Cmax={stats.average_makespan:.2f}"
            )

    result = run_genetic_algorithm(
        instance,
        config,
        progress_callback=None if args.quiet else report_progress,
    )

    if args.history_csv is not None:
        save_history(args.history_csv, result.history)

    order_one_based = " ".join(str(job + 1) for job in result.best.permutation)
    print()
    print(f"Instancja:          {instance.name} ({instance.jobs}x{instance.machines})")
    print(f"Procesy robocze:    {config.workers}")
    print(f"Najlepszy Cmax:     {result.best.makespan}")
    print(f"Kolejnosc zadan:    {order_one_based}")
    print(f"Czas obliczen [s]:  {result.elapsed_seconds:.3f}")
    if args.history_csv is not None:
        print(f"Historia:           {args.history_csv.resolve()}")


if __name__ == "__main__":
    # Niezbedne dla bezpiecznego uruchamiania ProcessPoolExecutor w Windows.
    main()

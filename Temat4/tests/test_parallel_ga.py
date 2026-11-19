import random
import unittest

from parallel_ga import (
    FlowShopInstance,
    GAConfig,
    calculate_makespan,
    order_crossover,
    run_genetic_algorithm,
    swap_mutation,
)


SMALL_INSTANCE = FlowShopInstance(
    name="test-6x3",
    processing_times=(
        (2, 3, 4),
        (1, 4, 2),
        (3, 2, 5),
        (4, 1, 3),
        (2, 5, 1),
        (5, 2, 2),
    ),
)


class GeneticOperatorsTests(unittest.TestCase):
    def test_makespan_for_known_order(self) -> None:
        times = ((2, 3), (1, 4), (3, 2))
        self.assertEqual(calculate_makespan((0, 1, 2), times), 11)

    def test_order_crossover_always_returns_a_permutation(self) -> None:
        parent_a = tuple(range(12))
        parent_b = tuple(reversed(parent_a))

        for seed in range(50):
            child = order_crossover(parent_a, parent_b, random.Random(seed))
            self.assertEqual(sorted(child), list(parent_a))

    def test_swap_mutation_preserves_all_genes(self) -> None:
        original = tuple(range(10))
        mutated = swap_mutation(original, 1.0, random.Random(7))
        self.assertEqual(sorted(mutated), list(original))
        self.assertNotEqual(mutated, original)


class ParallelAlgorithmTests(unittest.TestCase):
    def test_elitism_makes_best_history_non_increasing(self) -> None:
        config = GAConfig(
            population_size=16,
            generations=8,
            tournament_size=3,
            elite_count=2,
            workers=1,
            seed=99,
        )
        result = run_genetic_algorithm(SMALL_INSTANCE, config)
        best_values = [stats.best_makespan for stats in result.history]

        self.assertEqual(len(result.best.permutation), SMALL_INSTANCE.jobs)
        self.assertEqual(sorted(result.best.permutation), list(range(SMALL_INSTANCE.jobs)))
        self.assertTrue(
            all(later <= earlier for earlier, later in zip(best_values, best_values[1:]))
        )

    def test_parallel_and_reference_mode_are_reproducible(self) -> None:
        common = dict(
            population_size=12,
            generations=5,
            tournament_size=3,
            elite_count=2,
            seed=1234,
        )
        sequential = run_genetic_algorithm(
            SMALL_INSTANCE, GAConfig(workers=1, **common)
        )
        parallel = run_genetic_algorithm(
            SMALL_INSTANCE, GAConfig(workers=2, **common)
        )

        self.assertEqual(parallel.best, sequential.best)
        self.assertEqual(parallel.history, sequential.history)


if __name__ == "__main__":
    unittest.main()

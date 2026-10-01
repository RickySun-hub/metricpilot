"""Standard-library score intervals and an exact df=1 chi-square survival function."""
from math import erfc, hypot, sqrt
from statistics import NormalDist


def wilson(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError("Invalid binomial counts")
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    p = successes / n
    scale = 1 + z * z / n
    center = (p + z * z / (2 * n)) / scale
    margin = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / scale
    return center - margin, center + margin


def newcombe(c: int, nc: int, t: int, nt: int) -> tuple[float, float]:
    """Newcombe method 10, difference=treatment-control, without continuity correction."""
    lc, uc = wilson(c, nc)
    lt, ut = wilson(t, nt)
    pc, pt = c / nc, t / nt
    difference = pt - pc
    return difference - hypot(pt - lt, uc - pc), difference + hypot(ut - pt, pc - lc)


def srm_pvalue(control: int, treatment: int) -> float:
    n = control + treatment
    if n <= 0:
        raise ValueError("No assigned users")
    expected = n / 2
    statistic = (control - expected) ** 2 / expected + (treatment - expected) ** 2 / expected
    return erfc(sqrt(statistic / 2))

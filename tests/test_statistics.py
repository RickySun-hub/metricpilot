import pytest
from backend.statistics import newcombe, srm_pvalue, wilson
from scipy.stats import chisquare
from statsmodels.stats.proportion import confint_proportions_2indep, proportion_confint

@pytest.mark.parametrize('control,nc,treatment,nt', [(0, 10, 1, 12), (10, 10, 12, 12), (7, 31, 18, 50), (0, 100, 0, 100)])
def test_sparse_newcombe_matches_trusted_implementation(control, nc, treatment, nt):
    actual = newcombe(control, nc, treatment, nt)
    expected = confint_proportions_2indep(treatment, nt, control, nc, method='newcomb', compare='diff')
    assert actual == pytest.approx(expected, abs=1e-12)

@pytest.mark.parametrize('successes,n', [(0, 5), (5, 5), (3, 17)])
def test_wilson_matches_trusted_implementation(successes, n):
    assert wilson(successes, n) == pytest.approx(proportion_confint(successes, n, method='wilson'), abs=1e-12)

@pytest.mark.parametrize('control,treatment', [(50, 50), (70, 30), (501, 499)])
def test_srm_matches_chisquare(control, treatment):
    assert srm_pvalue(control, treatment) == pytest.approx(chisquare([control, treatment]).pvalue, abs=1e-12)

@pytest.mark.parametrize('successes,n', [(2, 1), (-1, 10), (0, 0)])
def test_invalid_binomial_rejected(successes, n):
    with pytest.raises(ValueError):
        wilson(successes, n)
